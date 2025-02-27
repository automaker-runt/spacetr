# logic

import time, json, queue
import threading
from typing import Union

from core.agent import Agent
from core.contracts import Contract
from core.shiphandler import ShipHandler
from core.ships import Ship
from core.thr.actf import ActionFinder
from core.thr.ctrct import ContractLogic
from core.utils import netw
from core.utils.objmanager import ObjManager
from core.waypoints import Waypoint
from fsys.io import jsonf
from hkeep.error import tb
from handler.sql import SqlHand
from hkeep.log.logger import get_logger
from netw.httpsession import HttpSession
from settings.settings import Config
from utils.strings import uptick
from utils.strings.shorten import short


class Core:

	_log = get_logger(__name__)

	
	def __init__(self,
					NetwSession:HttpSession,
					Conf:Config,
					SqlHan:SqlHand,
					logic_event_quit:threading.Event,
					main_thr_events,
					wake_up_qs,
					main_threads):
		
		self.logic_event = logic_event_quit
		self.core_terminated_event = threading.Event()
		self.Objman = ObjManager(	NetwSession,
									SqlHan,
									Conf,
									self.logic_event,
									self.core_terminated_event)

		self.main_thr_events = main_thr_events
		self.wake_up_qs = wake_up_qs
		self.main_threads = main_threads

		self.core_threads = list()
		self.core_thr_events = list()

		self.ShipHandlers = dict()
		self.Agent = None

		self.core()
				

	def core(self):

		# wait almost indefinitely for a successfull ping to "https://api.spacetraders.io/v2"
		waited = False
		start_ti = int(time.time())
		while not self.Objman.get(self.Objman.Conf.config["sites"]["SPACETRADERS"]["GET"]["PING"])[0]:
			waited = True
			time.sleep(5)
			if self.logic_event.is_set():
				return
			time.sleep(5)

		if waited:
			self.__class__._log.info(f"core proceded with start after waiting for API to be accessible for {int(time.time())-start_ti}s")

		self.start()

		# pathfinding should be a method/function, not a thread

		# setup Events to signal quitting
		trade_logic_event = threading.Event()
		contract_logic_event = threading.Event()
		actionfinder_logic_event = threading.Event()

		self.main_thr_events.append(self.logic_event)
		self.main_thr_events.append(trade_logic_event)
		self.main_thr_events.append(contract_logic_event)
		self.main_thr_events.append(actionfinder_logic_event)

		# setup logic threads
		self.core_thr_events.append(trade_logic_event)
		self.core_thr_events.append(contract_logic_event)
		self.core_thr_events.append(actionfinder_logic_event)

		# contract
		contract_logic_dict = dict()
		ctrct_logi = ContractLogic(self.Objman, contract_logic_dict, contract_logic_event)
		self.core_threads.append(ctrct_logi.thr)

		# ActionFinder
		actf_Q = queue.Queue()
		actf_logi = ActionFinder(self.Objman, self.ShipHandlers, contract_logic_dict, actf_Q, actionfinder_logic_event)
		self.core_threads.append(actf_logi.thr)

		# TODO:
		# make Task Object, implement tasks table in scheme.ex...
		# go with pandas for calc_hoops in Task

		self.__class__._log.info(f"[t_core] instantiated with id {threading.get_ident()}")

		# start main logic loop
		while not self.logic_event.is_set():


			time.sleep(1)

		# close thread Connections
		# close open DB connections
		if not self.Objman.Sqhlhan.ConnHandler.remove_thr_conns():
			self.__class__._log.error(f"core failed closing all thread Connections to DB {short(self.Objman.Sqhlhan.dbfp)}")

		for ev in self.core_thr_events:
			self.main_thr_events.remove(ev)
			ev.set()

		self.core_thr_events.clear()

		for t in self.core_threads:
			# in case of is_fresh_reset one thread will most likely
			# burn through timeout, since it is a deadlock between this
			# join and it's wait to get signal 
			t.join(self.Objman.Conf.config["THREAD_CORE_JOIN_TIMEOUT"])

			if t.is_alive():
				self.__class__._log.error(f"thread '{t.name}' failed to self-close")
				# TODO collect all zombie threads in a list

			if t in self.main_threads:
				self.main_threads.remove(t)

		self.core_terminated_event.set()
		time.sleep(1)

		if not self.logic_event.is_set():
			time.sleep(10)
			# need to restart
			# threading.Thread(target=self.core, name="t_core", daemon=False).start()
			self.core()
		else:
			self.__class__._log.info(f"[t_core] closed")


	def start(self) -> bool:
		self.agent = Agent(self.Objman)

		fresh_start = False

		if ObjManager.is_fresh_reset(self.agent):
			# make new DB, upticking previous file name
			self.Objman.Sqhlhan.new_dbfp(uptick.filename(self.Objman.Sqhlhan.dbfp))
			ObjManager._is_fresh_reset_procedure_active = False

			if self.register_new_agent():
				fresh_start = True
				
			else:
				self.__class__._log.critical(f"Aborting due to lack of Agent")

				raise Exception("No Agent available")
		
		elif self.agent is None:
			self.__class__._log.critical(f"Aborting due to lack of Agent")

			raise Exception("No Agent available")

		ShipH = ShipHandler(self.Objman, fleet_name="1", agent_total=self.agent.data["shipCount"])
		self.ShipHandlers.update({ShipH.fleet: ShipH})

		self.systems = {ShipH.fleet_sys: Waypoint.api_get_all_sys_wp(self.Objman, ShipH.fleet_sys)}

		if fresh_start:
			self.fresh_start_procedure()


	def register_new_agent(self, attempt:int=0) -> bool:
		pass
		url, data = self.Objman.Conf.config["sites"]["SPACETRADERS"]["POST"]["REGISTER"]
		data.update({"symbol": "ASIDE_"+set(self.Objman.Conf.config["CALLSIGN_SUFX"]).copy().pop(), "faction": set(self.Objman.Conf.config["FACTIONS"]).copy().pop()})
		
		suc, re = self.Objman.post(url=url, data=data)

		if not suc:
			self.__class__._log.error("register_new_agent failed")
			if attempt < 5:
				time.sleep(3)

				return self.register_new_agent(attempt+1)

			else:
				self.__class__._log.error(f"register_new_agent failed registering new Agent after {attempt} attempts")
				
				return False

		self.__class__._log.info("New Agent registered with Callsign '{}' for faction '{}'".format(data["symbol"], data["faction"]))
		
		re_dec = re.Response.json()

		bearer = jsonf.load(".env")[1]
		bearer.update({"AGENT": {"Authorization": "Bearer "+re_dec["data"]["token"]}})
		self.Objman.Netwsess.set_auth_header(header=bearer["AGENT"], host="spacetraders.io")

		headq_val = {
						"factions": re_dec["data"]["faction"]["symbol"],
						"waypoints_id": None,		# only have system
						"systemsymbol": re_dec["data"]["faction"]["headquarters"],
						"updated": int(time.time())
		}

		# insert faction HQ
		if not self.Objman.ins("headq", list(headq_val.values())):
			self.__class__._log.error(f"register_new_agent failed inserting new headq {headq_val}")

			return False

		# set Agent
		self.agent = Agent(self.Objman, data=re_dec["data"]["agent"])
		# for some reason shipCount is probably set to 0
		# so need to change that for ShipHandler to work
		if self.agent.data["shipCount"] == 0:
			self.agent.data["shipCount"] = 2
		self.agent.insert()

		return True


	def fresh_start_procedure(self):
		# accept contract

		# go to ENGINEERED_ASTEROID with main ship and extract

		pass


def core_test(Objmanager):
	# starts core game procedures

	_log = get_logger(__name__)


	ShipH = ShipHandler(Objmanager, fleet_name="1")

	# print(len(Waypoint.get_all_sys_wp(Objmanager, ShipH.fleet_sys)))

	shippy = list(ShipH.inventory.values())[0]

	db_state = shippy.jj.copy()
	db_state["modules"] = shippy.jj["modules"].copy()

	res = None

	# for mod in shippy.jj["modules"]:
	# 	if shippy.jj["modules"].count(mod) > 1:
	# 		print("suc")
	# 		res = mod

	shippy.jj["modules"].append(shippy.jj["modules"][0])
	
	print(shippy.update_ship(db_state))

	print("diff", shippy.jj["modules"] == db_state["modules"], len(shippy.jj["modules"]), len(db_state["modules"]))

	print(list(i["symbol"] for i in shippy.jj["modules"]))
