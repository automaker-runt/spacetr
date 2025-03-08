# tasks
import time
import threading
from typing import Union

from core.ships import Ship
from core.utils import dfop
from core.utils.coord import GameCoord, distance
from core.utils.marketdata import cycle
from core.utils.objmanager import ObjManager
from core.waypoints import Waypoint
from hkeep.log.logger import get_logger
from utils.time import wait, ISO_to_epoch


class PreTask:

	_log = get_logger(__name__)

	PT_list = list()


	def __init__(self, Objman:ObjManager,
						id_:str,
						tsk_item,
						tsk_type:str,
						sys:str,
						GmCrd_dict:dict,
						extras: Union[None, dict]=None,
						prio:int=100):

		'''
		tsk_item: Union[Contract, Trade, Extraction, Haul, Marketdata]
		tsk_type: "contract", "trade", "extract", "haul", "marketdata"
		'''
		self.Objman = Objman
		self.id_ = id_
		self.tsk_item = tsk_item
		self.tsk_type = tsk_type
		self.sys = sys
		self.GmCrd_dict = GmCrd_dict
		self.prio = prio
		self.extras = extras

		self.ship = None
		self.schedule = None
		self.df_sys_wps = None
		self.df_shps = None

		if self not in self.__class__.PT_list:
			self.__class__.PT_list.append(self)


	def expired(self, Mrkt, Shps) -> bool:
		# possibly returns True for marketdata PreTask
		if self.tsk_type != "marketdata":
			return False

		# if the cycle exists already in Mrkt
		# TODO


	# make Obj list.sort()-able
	def __lt__(self, other):
		return self.prio < other.prio


class Task:

	_log = get_logger(__name__)

	T_list = list()


	def __init__(self, PT:PreTask,
						Mrkt,
						prio: Union[int, None]=None):
		
		PT.ship.has_task = True
		PT.ship.task_id = PT.id_
		PT.ship._update_state()
		self.PT = PT
		self.Mrkt = Mrkt
		self.prio = prio if prio is not None else PT.prio

		if self not in self.__class__.T_list:
			self.__class__.T_list.append(self)

		# PT.schedule?

		self.ev_quit = threading.Event()
		self.thr = threading.Thread(target=self.work, name=f't_{self.tsk_type[0].upper()}Tsk_{self.id_[-5:]}', daemon=False)
		self.thr.start()

		self.__class__._log.info(f"new {str(self)}")

		self.extra_init()

	
	def __str__(self) -> str:
		pass


	@property
	def id_(self) -> str:
		return self.PT.id_

	@property
	def Objman(self) -> ObjManager:
		return self.PT.Objman

	@property
	def ship(self) -> Ship:
		return self.PT.ship

	@property
	def tsk_item(self):
		return self.PT.tsk_item

	@property
	def tsk_type(self) -> str:
		return self.PT.tsk_type

	@property
	def sys(self):
		return self.PT.sys

	@property
	def GmCrd_dict(self) -> dict:
		'''
		can hold keys: "sell", "mine", "deliver", "marketdata"
		'''
		return self.PT.GmCrd_dict

	@property
	def extras(self) -> dict:
		return self.PT.extras

	@property
	def df_sys_wps(self):
		return self.PT.df_sys_wps

	# needs caution, because it may be outdated ships dataframe
	@property
	def df_shps(self):
		return self.PT.df_shps

	@property
	def flight_mode(self):
		if self.ship.frame.lower() == "frigate":
			return self.Objman.Conf.config["FLIGHT_MODE_FRIGATES"]
		elif self.ship.frame.lower() == "probe":
			return "CRUISE"

	@property
	def go(self) -> bool:
		if not self.ev_quit.is_set():	
			return True
		else:
			return False


	def __lt__(self, other):
		return self.prio < other.prio


	def extra_init(self):
		pass


	def work(self):
		# find out the type of PT, take according measures
		pass


	def check_markets(self):
		if self.go:
			# find out if current waypoint has shipyard or marketplace to know what to query
			if ("SHIPYARD" in self.df_sys_wps.loc[self.df_sys_wps["wp_symbol"] == self.ship.waypoint, "traits"].iloc[0] and
				self.market_is_outdated()):
				
				assert self.get_shipmarketdata(), f"Error get_shipmarketdata {str(self)}"
			
			if ("MARKETPLACE" in self.df_sys_wps.loc[self.df_sys_wps["wp_symbol"] == self.ship.waypoint, "traits"].iloc[0] and
				self.market_is_outdated()):
				
				assert self.get_marketdata(), f"Error get_marketdata {str(self)}"


	def get_shipmarketdata(self):
		# queries for shipyard data
		# attempts to insert new ships

		url = self.Objman.Conf.config["sites"]["SPACETRADERS"]["GET"]["SHIPYARD_DATA"].format(systemSymbol=self.sys, WaypointSymbol=self.ship.waypoint)
		suc, re = self.Objman.get(url=url)

		if not suc: 
			self.__class__._log.error(f"[{self.thr.name}] failed get_shipmarketdata {str(self)}")
			
			return False

		re_dec = re.Response.json()

		if (self.Mrkt.new_mkt_entries(re_dec["data"]["ships"], self.ship.waypoint, inp_type="ship") and
			True): #self.Mrkt.new_trd_entries(re_dec["data"]["transactions"], self.ship.waypoint)):
			
			return True

		return False


	def get_marketdata(self) -> bool:
		# queries for marketdata
		# attempts to insert new goods

		url = self.Objman.Conf.config["sites"]["SPACETRADERS"]["GET"]["MARKETPLACE_DATA"].format(systemSymbol=self.sys, WaypointSymbol=self.ship.waypoint)
		suc, re = self.Objman.get(url=url)

		if not suc: 
			self.__class__._log.error(f"[{self.thr.name}] failed get_marketdata {str(self)}")
			
			return False

		re_dec = re.Response.json()

		if (self.Mrkt.new_mkt_entries(re_dec["data"]["tradeGoods"], self.ship.waypoint) and
			self.Mrkt.new_trd_entries(re_dec["data"]["transactions"], self.ship.waypoint)):
			
			return True

		return False


	def market_is_outdated(self, wp_sym: Union[str, None]=None) -> bool:
		if wp_sym is None:
			wp_sym = self.ship.coordinates.wp

		cycl = cycle(self.Objman.Conf.config["MARKETDATA_CYCLE"])
		
		# check if ships current waypoint is in self.Mrkt.df, if so lookup updated if it is outdated
		# taking max out of all updated values for the waypoint to see when last update was made
		if (self.Mrkt.df["waypoint"].isin([wp_sym]).any() and
			self.Mrkt.df.loc[self.Mrkt.df["waypoint"] == wp_sym, "updated"].max() >= cycl):

			return False

		return True


	def shp_dwnti_func(self, jj:dict) -> None:
		# blocks the thread until either
		# - cooldown runs up
		# - arrival passed
		if "cooldown" in jj and "expiration" in jj["cooldown"]:
			wait(ISO_to_epoch(jj["cooldown"]["expiration"]), interval=1.0, ev_quit=self.ev_quit)

		if "nav" in jj and "route" in jj["nav"]:
			wait(ISO_to_epoch(jj["nav"]["route"]["arrival"]), interval=1.0, ev_quit=self.ev_quit)


	def journey_waypoint(self, coord:GameCoord, mode:str="CRUISE") -> bool:
		'''
		does the route planning + refueling
		'''
		if self.go and self.ship.frame.lower() == "probe":
			return self.ship.go_waypoint(coord=coord, mode="CRUISE", dwnti_func=self.shp_dwnti_func)

		# we can empty our tank, because we can buy fuel there
		if (self.go and
			dfop.wp_type_traits_lookup(self.df_sys_wps, ["FUEL_STATION"], ["MARKETPLACE"]).wp_symbol.isin([coord.wp]).any()):

			# check for range with reduced reserve at current fuel tank level
			if self.go and self.ship.in_range(coord, mode=mode, reserve=0.01):
				return self.ship.go_waypoint(coord=coord, mode=mode, dwnti_func=self.shp_dwnti_func)

			# now check if we can go there with max fuel tank
			# from the nearest place (even where we are now, with fuel)
			elif self.go:
				# find nearest place to get full tank
				coord_b = dfop.nearest(dfop.wp_type_traits_lookup(self.df_sys_wps, ["FUEL_STATION"], ["MARKETPLACE"]),
										self.ship.coordinates)

				# only if coord_b is in range
				if self.go and self.ship.in_range(coord_b, mode=mode, reserve=0.01):
					# check if one can go from there emptying the tank
					if self.go and self.ship.in_range(coord,
														mode=mode,
														current_fuel=self.ship.fuelCapacity,
														reserve=0.01,
														coord_b=coord_b):

						if self.go and coord_b.wp != self.ship.waypoint:
							# go to coord_b
							if not self.ship.go_waypoint(coord=coord_b, mode=mode, dwnti_func=self.shp_dwnti_func):
								return False
						# refuel to max at coord_b
						if self.go and not self.ship.refuel(dwnti_func=self.shp_dwnti_func):
							return False

						if self.go:
							return self.ship.go_waypoint(coord=coord, mode=mode, dwnti_func=self.shp_dwnti_func)

					# need to calculate furthest hop in direction of coord

				# coord_b, being the nearest to get full tank from current position, is out of range with reserve=0.01
				# need to go by mode="DRIFT"
				elif self.go:
					return self.ship.go_waypoint(coord=coord, mode="DRIFT", dwnti_func=self.shp_dwnti_func)

		return True

		
	
class ContractTask(Task):


	

	@property
	def inv_full(self) -> bool:
		# whether inventory is too full to extract
		if self.ship.cargoCapa < self.ship.cargoUnits +4:
			return True
		else:
			return False

	@property
	def inv_ctrct_good_units(self) -> int:
		# get how many of the contract goods are in inventory
		units = next((i["units"] for i in self.ship.cargoInv if i["symbol"] == self.extras["good"]["tradeSymbol"]), 0)
		return units

	@property
	def ctrct_fulf(self) -> bool:
		# whether got enough good in storage to fulfill contract
		if self.extras["good"]["unitsRequired"] <= self.extras["good"]["unitsFulfilled"] + self.inv_ctrct_good_units:
			return True
		else:
			return False


	def __str__(self) -> str:
		return f"<ContractTask {self.id_} {self.extras["good"]["unitsRequired"]} {self.extras["good"]["tradeSymbol"]} delivery at {self.GmCrd_dict["deliver"]} Ship:{str(self.ship)}>"


	def extra_init(self):
		pass


	def work(self):

		self.__class__._log.info("[{}] instantiated with id %(threadID)s".format(self.thr.name), {"threadID": threading.get_ident(), "_msg_args": ["arg", "value"]})

		# wait for the ship to be ready to receive commands
		self.shp_dwnti_func(self.ship.jj)

		finished = False

		while self.go:
			time.sleep(1)
		while self.go and not finished:
			start_ti = int(time.time())

			# go deliver if done
			if self.go and self.ctrct_fulf:
				finished = True

			# if ship has full cargo, decide what to do with it
			if self.go and self.inv_full:
				pass
				# either or comobination of
				# go to marketplace and sell, if near delivery wp -> go and deliver if it is a great chunk of storage already
				# jettison

				# if going to deliver self.extras["good"] needs to be updated

			# if ship is where it is supposed to mine
			# mine (aka extract)
			if self.go and self.ship.waypoint == self.GmCrd_dict["mine"].wp:
				assert self.ship.extract_ores(dwnti_func=self.shp_dwnti_func), f"Error ship.extract_ores {str(self)}"

			# if ship is not where it is mining, move it there
			elif self.go and self.ship.waypoint != self.GmCrd_dict["mine"].wp:
				assert self.journey_waypoint(self.GmCrd_dict["mine"], mode=self.flight_mode), "Error journey_waypoint to '{}' {}".format(str(self.GmCrd_dict["mine"]), str(self))
				# check if ship could refuel (has 100+ less than full capacity, 1 fuel at MARKETPLACE = 100 fuel capacity)

			# make wait if nothing happened (for some reason -> ?)
			if self.go and start_ti+int(self.Objman.Conf.config["THREAD_TASK_INTERVAL"]) > int(time.time()):
				time.sleep(self.Objman.Conf.config["THREAD_TASK_INTERVAL"])

		# realease ship
		self.ship.has_task = False
		self.ship.task_id = None
		self.ship._update_state()

		# close open DB connections
		if not self.Objman.Sqhlhan.ConnHandler.remove_thr_conns():
			self.__class__._log.error(f"[{self.thr.name}] work failed closing all thread Connections to DB {short(self.Objman.Sqhlhan.dbfp)}")

		if not finished:	
			self.__class__._log.info(f"[{self.thr.name}] ended")
		else:
			self.__class__._log.info(f"[{self.thr.name}] finished")


class MarketdataTask(Task):


	def __str__(self) -> str:
		wps = str()

		for i in self.GmCrd_dict["li_markets"]:
			wps += str(i)+", "

		wps = wps[:-2]

		return f"<MarketdataTask {self.id_} {wps} Ship:{str(self.ship)}>"


	def extra_init(self):
		pass


	def work(self):

		self.__class__._log.info("[{}] instantiated with id %(threadID)s".format(self.thr.name), {"threadID": threading.get_ident(), "_msg_args": ["arg", "value"]})

		# wait for the ship to be ready to receive commands
		self.shp_dwnti_func(self.ship.jj)

		# query data where we are right now if available
		self.check_markets()

		finished = False

		while self.go and not finished:
			start_ti = int(time.time())

			if len(self.GmCrd_dict["li_markets"]) == 0:
				finished = True
				continue
						
			# [0] is distance, [1] is GmCrd
			coord = self.GmCrd_dict["li_markets"].pop(0)

			# check again if market needs updating where ship is sent
			if not self.market_is_outdated(coord.wp):
				continue

			# catch fails
			if self.ship.waypoint == coord.wp:
				self.__class__._log.warning(f"[{self.thr.name}] tried sending ship where it already is")
				continue

			# go to coord
			if self.go:
				assert self.ship.go_waypoint(coord=coord, dwnti_func=self.shp_dwnti_func), f"Error ship.go_waypoint {str(self)}"

			if self.go:
				# find out if current waypoint has shipyard or marketplace to know what to query
				self.check_markets()


			# make wait if nothing happened (for some reason -> ?)
			if self.go and start_ti+int(self.Objman.Conf.config["THREAD_TASK_INTERVAL"]) > int(time.time()):
				time.sleep(self.Objman.Conf.config["THREAD_TASK_INTERVAL"])

		# realease ship
		self.ship.has_task = False
		self.ship.task_id = None
		self.ship._update_state()

		# close open DB connections
		if not self.Objman.Sqhlhan.ConnHandler.remove_thr_conns():
			self.__class__._log.error(f"[{self.thr.name}] work failed closing all thread Connections to DB {short(self.Objman.Sqhlhan.dbfp)}")

		if not finished:	
			self.__class__._log.info(f"[{self.thr.name}] ended")
		else:
			self.__class__._log.info(f"[{self.thr.name}] finished")
