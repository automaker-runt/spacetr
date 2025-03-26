# actf
# logic to find the best PreTask to make a Task for
import time, queue, json
import threading

from core.tasks import PreTask, Task, ContractTask, MarketdataTask
from core.utils import dfop
from core.utils.coord import distance
from core.utils.objmanager import ObjManager
from core.waypoints import Waypoint
from hkeep.log.logger import get_logger
from utils.strings.shorten import short


class ActionFinder:


	_log = get_logger(__name__)


	def __init__(self, Objman:ObjManager,
						Ships,
						Mrkt,
						ShipH:dict,
						Q_out:queue.Queue,
						ev_quit:threading.Event):
		'''
		"scrolls" through PreTasks and finds adequate Task for self.Ships.df nearby PreTask,
		then produces a Task for the respective Ship and starts the Task,
		giving control of the Ship to the Task
		'''
		self.Objman = Objman
		self.Ships = Ships
		self.Mrkt = Mrkt
		self.ShipH = ShipH
		self.Q_out = Q_out
		self.ev_quit = ev_quit

		self.history = list()

		self.thr = threading.Thread(target=self.actf_logic, args=(ev_quit,), name='t_actf_logi', daemon=False)
		self.thr.start()


	def actf_logic(self, ev_quit:threading.Event):

		# if not checking first for has_task, self.Ships.df might not be updated yet, producing exception
		avail_shps = lambda x: "has_task" in x.columns and len(x.loc[~x["has_task"]]) > 0
		sys_wps = dict()
		
		self.__class__._log.info("[{}] instantiated with id %(threadID)s".format(self.thr.name), {"threadID": threading.get_ident(), "_msg_args": ["arg", "value"]})

		while not ev_quit.is_set():

			self.Ships.init_ships_df()

			# if nothing to do, just wait			
			if not avail_shps(self.Ships.df) or len(PreTask.PT_list) == 0:
				time.sleep(2)
				continue
			
			PreTask.PT_list.sort()

			# TODO implement in a way, that if a task is not immediately taken (e.g. "contract" not taken because no mine_shps available)
			# task is put back in PT_list and the next task of different kind is taken to be made into Task if apropiate conditions are fulfilled 
			popped = list()
			popped.append(PreTask.PT_list.pop(0))

			if popped[0].expired(self.Mrkt, self.Ships.df):
				continue
			
			# TODO track time left until has_task turns False, so according to ship distance to contract, maybe most efficient is
			# waiting some time for a ship right nearby to finish it's Task, rather than making a ship that is free right now
			# travel across system

			mine_shps = dfop.mine_shps(self.Ships.df)

			# contract mine
			if popped[-1].tsk_type in ("contract", "mine") and len(mine_shps) > 0:
				
				# delist PT from popped, we will create Task with it
				PT = popped.pop(-1)

				if PT.sys not in sys_wps:
					sys_wps[PT.sys] = Waypoint.get_sys_wp_df(self.Objman, PT.sys)

				# give PreTask dataframes
				PT.df_sys_wps = sys_wps[PT.sys]
				# TODO possibly the df might change and won't get the new reference
				PT.df_shps = self.Ships.df
				
				# get good that is needed to fulfill contract
				good = PT.extras["good"]["tradeSymbol"]
				if good in self.Objman.Conf.config["GOOD_TRAIT_MAP"]:
					traits_lookup = self.Objman.Conf.config["GOOD_TRAIT_MAP"][good]
				else:
					self.__class__._log.critical(f"actf_logic failed to link needed good to trait to search in waypoints for due to good '{good}' not found in mapping")
					# send whole ActionFinder to sleep
					while good not in self.Objman.Conf.config["GOOD_TRAIT_MAP"]:
						time.sleep(2)

					traits_lookup = self.Objman.Conf.config["GOOD_TRAIT_MAP"][good]

				# gather waypoints with necessary traits from traits_lookup 
				# from https://stackoverflow.com/a/17973255
				# when not deep copying, warning gets printed about SettingWithCopyWarning when I later use apply with lambda on this df
				poi_wps = dfop.traits_lookup(sys_wps[PT.sys], traits_lookup)

				# check if one of them even has MARKETPLACE (like on ENGINEERED_ASTEROID)
				mrkt_check = poi_wps[poi_wps["traits"].str.contains("MARKETPLACE", na=False)]
				if len(mrkt_check) > 0:
					pass

				# add distance from waypoints, with traits in traits_lookup, to delivery point
				poi_wps["dist_dlvr"] = poi_wps.apply(lambda x: distance(x.GmCrd, PT.GmCrd_dict["deliver"]), axis=1)

				# get the nearest mining waypoint with all columns
				mine_wp_dict = poi_wps[poi_wps["dist_dlvr"] == poi_wps["dist_dlvr"].min()].to_dict(orient="records")[0]
				PT.GmCrd_dict["mine"] = mine_wp_dict["GmCrd"]
				if "sell" not in PT.GmCrd_dict:
					PT.GmCrd_dict["sell"] = [mine_wp_dict["GmCrd"]]
				elif mine_wp_dict["GmCrd"] not in PT.GmCrd_dict["sell"]:
					PT.GmCrd_dict["sell"].append(mine_wp_dict["GmCrd"])

				# determine a ship for the PreTask
				if PT.ship is None:	
					mine_shps["dist_mine"] = mine_shps.apply(lambda x: distance(x.GmCrd, PT.GmCrd_dict["mine"]), axis=1)
					mine_ship_dict = mine_shps[mine_shps["dist_mine"] == mine_shps["dist_mine"].min()].to_dict(orient="records")[0]
					# grab Ship Obj
					PT.ship = self.Ships.get_ship(sym=mine_ship_dict["symbol"])

				# init Task
				T = ContractTask(PT, self.Mrkt)
				# add Task to threads lists


				# print()
				# print(mine_ship_dict)
				# print(Task.T_list)

				# TODO: 
				# - get all known waypoints, calculate paths according to fuel, create logic/system to get() from Task obj all needed actions
				# - create function to derive sub-tasks from major actions of Task
				# - implement filtering self.Ships.df also according to which ones will be available soon

				# calculate distance of each ship to


				# save PreTask.id_ in history, to not create another similar Task

			if len(popped) == 0:	
				if len(PreTask.PT_list) == 0:
					continue

				popped.append(PreTask.PT_list.pop(0))

			probe_shps = dfop.probe_shps(self.Ships.df)
			
			# marketdata endevour
			if popped[-1].tsk_type == "marketdata" and len(probe_shps) > 0:
				
				# delist PT from popped, we will create Task with it
				PT = popped.pop(-1)

				# determine a ship for the PreTask
				if PT.ship is None:
					probe_shps = dfop.nearest_multiple(probe_shps, PT.GmCrd_dict["li_markets"], "dist_wps", filter_same_coords=False)
					probe_shps["dist_wp_min"] = [min(j for j in i) for i in probe_shps.dist_wps.values]
					probe_ship_dict = probe_shps[probe_shps["dist_wp_min"] == probe_shps["dist_wp_min"].min()].to_dict(orient="records")[0]
					# grab Ship Obj
					PT.ship = self.Ships.get_ship(sym=probe_ship_dict["symbol"])

				if PT.sys not in sys_wps:
					sys_wps[PT.sys] = Waypoint.get_sys_wp_df(self.Objman, PT.sys)

				PT.df_sys_wps = sys_wps[PT.sys]
				PT.df_shps = self.Ships.df

				# init Task
				T = MarketdataTask(PT, self.Mrkt)


			# popped = list()
			# popped.append(self.PreTask.pop(0))
			# marketdata navigation purposes

			# readd all popped but not turned into Task
			PreTask.PT_list.extend(popped)

			time.sleep(self.Objman.Conf.config["THREAD_ACTF_LOGI_INTERVAL"])


		# send close signal to Task threads
		for Tsk in Task.T_list:
			Tsk.ev_quit.set()

		# wait for all Task threads to end
		for Tsk in Task.T_list:
			Tsk.thr.join(self.Objman.Conf.config["THREAD_TASK_JOIN_TIMEOUT"])
			if Tsk.thr.is_alive():
				self.__class__._log.warning(f"[{self.thr.name}] thread '{Tsk.thr.name}' failed to auto-close")

		# close open DB connections
		if not self.Objman.Sqhlhan.ConnHandler.remove_thr_conns():
			self.__class__._log.error(f"[{self.thr.name}] actf_logic failed closing all thread Connections to DB {short(self.Objman.Sqhlhan.dbfp)}")

		self.__class__._log.info(f"[{self.thr.name}] closed")
