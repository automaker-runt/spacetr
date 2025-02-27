# actf
# logic to find the best PreTask to make a Task for
import time, queue
import threading
import pandas as pd

from core.tasks import Task
from core.utils.objmanager import ObjManager
from hkeep.log.logger import get_logger


class ActionFinder:


	_log = get_logger(__name__)


	def __init__(self, Objman:ObjManager,
						ShipH:dict,
						contracts:dict,
						Q_out:queue.Queue,
						ev_quit:threading.Event):
		'''
		"scrolls" through PreTasks and finds adequate Task for Ships nearby PreTask,
		then produces a Task for the respective Ship and starts the Task,
		giving control of the Ship to the Task
		'''
		self.Objman = Objman
		self.ShipH = ShipH
		self.contracts = contracts
		self.Q_out = Q_out
		self.ev_quit = ev_quit

		self.history = list()

		self.thr = threading.Thread(target=self.actf_logic, args=(ev_quit,), name='t_actf_logi', daemon=False)
		self.thr.start()


	def actf_logic(self, ev_quit:threading.Event):

		self.__class__._log.info(f"[{self.thr.name}] instantiated with id {threading.get_ident()}")

		while not ev_quit.is_set():

			ships = self.get_ships_df()
			
			print(ships.columns)

			# if not checking first for has_task, ships might not be updated yet, producing exception
			if "has_task" in ships.columns and len(ships.loc[~ships["has_task"]]) > 0:
				
					
				# ships.mounts.apply(lambda x: any("MOUNT_MINING_LASER_" in item for item in x)) from https://stackoverflow.com/a/53342780
				mine_shps = ships[ships.mounts.apply(lambda x: any("MOUNT_MINING_LASER_" in item for item in x)) & 
									ships["nav.status"].isin(["DOCKED", "IN_ORBIT"]) & 
									ships["cooldown.expiration"].lt(int(time.time()))]
				# save PreTask.id_ in history, to not create another similar Task
				print()
				print(mine_shps)

				time.sleep(5)

			else:
				time.sleep(1)

			time.sleep(self.Objman.Conf.config["THREAD_ACTF_LOGI_INTERVAL"])
			# ships = 40


		# close open DB connections
		if not self.Objman.Sqhlhan.ConnHandler.remove_thr_conns():
			self.__class__._log.error(f"[{self.thr.name}] actf_logic failed closing all thread Connections to DB {short(self.Objman.Sqhlhan.dbfp)}")

		self.__class__._log.info(f"[{self.thr.name}] closed")


	def get_ships_df(self) -> pd.core.frame.DataFrame:
		ships = None

		for i in self.ShipH.values():
			if len(self.ShipH.values()) == 1 or ships is None:
				ships = i.sdf[0]

			else:
				ships = pd.concat(ships, i.sdf[0]).reset_index()

		return ships


	# deprecated
	def get_idle_mine_ships(self, ships_df:pd.core.frame.DataFrame) -> pd.core.frame.DataFrame:
		# ships = list()

		# for fleet, Obj in self.ShipH.items():
		# 	ships.extend(list(i for i in Obj.inventory.values() if (not i.has_task and
		# 															i.has_mount("MOUNT_MINING_LASER_") and
		# 															i.status in ("DOCKED", "IN_ORBIT") and
		# 															i.cooldown_exp < int(time.time()))))

		# ships = pd.concat((i.jj_to_df() for i in self.ShipH.values())).set_index("symbol")

		idle_mine_ships = ships_df

		return idle_mine_ships

