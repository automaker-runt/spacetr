# mrktd
# logic to find the right waypoints to gather marketdata
import time
import threading
import pandas as pd

from core.tasks import PreTask
from core.utils import dfop
from core.utils.coord import GameCoord
from core.utils.marketdata import cycle
from core.utils.objmanager import ObjManager
from core.waypoints import Waypoint
from hkeep.log.logger import get_logger
from utils.strings.shorten import short
from utils.strings.xxhash import getPureHash
from utils.time import e


class MarketdataLogic:


	_log = get_logger(__name__)


	def __init__(self, Objman:ObjManager, Mrkt, Ships, ev_quit:threading.Event):
		self.Objman = Objman
		self.Mrkt = Mrkt
		self.Ships = Ships
		self.ev_quit = ev_quit
		
		self.history = dict()

		self.thr = threading.Thread(target=self.mrktd_logic, args=(ev_quit,), name='t_mrktd_logi', daemon=False)
		self.thr.start()


	def send_on_nearest_trip(self, probe_shps, other_ships, mrktd_wps_GmCrd_li, nearest_amt:int) -> bool:
		# give every ship entry nearest coords in it's system
		other_ships_nearest = dfop.nearest_multiple(other_ships,
													mrktd_wps_GmCrd_li,
													new_col="nearest_coords",
													amt=nearest_amt)

		# flag to know if probes have PreTasks for other_ships_nearest
		setPT_other_ships_nearest = False

		# get current cycle representation as the first second epoch time
		cycl = cycle(self.Objman.Conf.config["MARKETDATA_CYCLE"])

		# create a PreTask for every free probe
		for _, coords in zip(range(len(probe_shps)), other_ships_nearest["nearest_coords"].to_list()):
			
			hash_id = str(cycl)
			coords_li = list()
			# each wp
			for coord in coords:
				# coord is a tuple consisting of [0] being distance and [1] being the GmCrd
				
				if coord[1].wp not in self.history:
					self.history[coord[1].wp] = list()
				
				# lookout for wp if update is needed and not already in self.history[wp]
				# or Mrkt updated already happened in this cycle
				if (cycl in self.history[coord[1].wp] or
						(self.Mrkt.df["waypoint"].isin([coord[1].wp]).any() and
						self.Mrkt.df.loc[self.Mrkt.df["waypoint"] == coord[1].wp, "updated"].max() >= cycl)):
					continue

				self.history[coord[1].wp].append(cycl)

				hash_id += coord[1].wp
				coords_li.append(coord[1])

			if len(coords_li) == 0:
				continue

			PreTask(self.Objman,
					getPureHash(hash_id),
					None,
					"marketdata",
					sys=coords_li[0].sys,
					GmCrd_dict={"li_markets": coords_li},
					extras={"cycle": cycl})

			setPT_other_ships_nearest = True

		return setPT_other_ships_nearest


	def mrktd_logic(self, ev_quit:threading.Event):
		last_check_wps = 0
		sys_wps = dict()
		avail_shps = lambda x: "has_task" in x.columns and len(x.loc[~x["has_task"]]) > 0
		
		self.__class__._log.info("[{}] instantiated with id %(threadID)s".format(self.thr.name), {"threadID": threading.get_ident(), "_msg_args": ["arg", "value"]})

		while not ev_quit.is_set():

			# periodically refresh the wp df
			if last_check_wps + self.Objman.Conf.config["THREAD_MRKTDF_LOGI_CHECK_WPS_INTERVAL"] < int(time.time()):
				for sys_sym in self.Ships.df["nav.systemSymbol"].unique():
					sys_wps[sys_sym] = Waypoint.get_sys_wp_df(self.Objman, sys_sym)

			# if probes available without task			
			if avail_shps(self.Ships.df):

				probe_shps = dfop.probe_shps(self.Ships.df)

				if len(probe_shps) > 0:

					# get all non probe ships, no matter their current activity or system
					other_ships = dfop.any_non_probe_shps(self.Ships.df)

					# get all system waypoints of systems where free drones are
					mrktd_wps = pd.concat(list(sysdf for sys, sysdf in sys_wps.items() if sys in probe_shps["nav.systemSymbol"].unique() and sys in other_ships["nav.systemSymbol"].unique()))
					# only waypoints with MARKETPLACE and SHIPYARD trait
					mrktd_wps = dfop.traits_lookup(mrktd_wps, ["SHIPYARD", "MARKETPLACE"])

					# remove duplicates from mrktd_wps
					mrktd_wps = mrktd_wps.drop_duplicates(["coords"])

					amt = 2
					while not self.send_on_nearest_trip(probe_shps,
														other_ships,
														mrktd_wps["GmCrd"].to_list(),
														amt):
						amt += 1

			# filter waypoints only for MARKETPLACE and SHIPYARD, 
			# filter ships only for non probes
			# filter if they have been updated in last 30min(variable)
			# and create a PreTask for that waypoint+timestamp as PreTask id_
				

			time.sleep(self.Objman.Conf.config["THREAD_MRKTDF_LOGI_INTERVAL"])

		# close open DB connections
		if not self.Objman.Sqhlhan.ConnHandler.remove_thr_conns():
			self.__class__._log.error(f"[{self.thr.name}] mrktd_logic failed closing all thread Connections to DB {short(self.Objman.Sqhlhan.dbfp)}")

		self.__class__._log.info(f"[{self.thr.name}] closed")
