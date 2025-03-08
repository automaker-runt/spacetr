# logic

import time, json, queue, copy, random
import threading
import pandas as pd
from typing import Union

from core.agent import Agent
from core.contracts import Contract
from core.shiphandler import ShipHandler
from core.marketdata import Market
from core.thr.actf import ActionFinder
from core.thr.ctrct import ContractLogic
from core.thr.mrktd import MarketdataLogic
from core.utils import netw
from core.utils.objmanager import ObjManager
from core.waypoints import Waypoint
from fsys.io import jsonf
from hkeep.error import tb
from handler.sql import SqlHand
from hkeep.log.logger import get_logger
from netw.httpsession import HttpSession
from netw.response import Response
from settings.settings import Config
from utils.strings import uptick
from utils.strings.shorten import short


class Ships:


	def __init__(self, ShipH:dict):
		self.ShipH = ShipH
		self.df = None
		self.init_ships_df()


	def init_ships_df(self) -> pd.core.frame.DataFrame:
		ships = None

		for i in self.ShipH.values():
			if len(self.ShipH.values()) == 1 or ships is None:
				ships = i.sdf[0]

			else:
				ships = pd.concat(ships, i.sdf[0]).reset_index()

		if ships is None:
			ships = pd.DataFrame()

		self.df = ships


	def get_ship(self, sym:str):
		# returns the Ship Obj
		return next(i.inventory[sym] for i in self.ShipH.values() if sym in i.inventory)


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

		# need to set this in case Objman encounters fresh reset
		# to prevent deadlock while it waits for t_core to complete Agent()
		# while that doesn't complete because Objman waits t_core to be stopped
		self.core_terminated_event.set()

		self.main_thr_events = main_thr_events
		self.wake_up_qs = wake_up_qs
		self.main_threads = main_threads

		self.core_threads = list()
		self.core_thr_events = list()

		self.ShipHandlers = dict()

		self.core()
				

	def core(self):

		Response.forbidden = False
		# wait almost indefinitely for a successfull ping to "https://api.spacetraders.io/v2"
		waited = False
		start_ti = int(time.time())
		while not self.logic_event.is_set() and not self.Objman.get(self.Objman.Conf.config["sites"]["SPACETRADERS"]["GET"]["PING"])[0]:
			waited = True
			time.sleep(10)
			if self.logic_event.is_set():
				return
			time.sleep(10)

		if waited:
			self.__class__._log.info(f"core proceded with start after waiting for API to be accessible for {int(time.time())-start_ti}s")

		if self.logic_event.is_set():
			return

		# get a persistent conn for this thread
		self.Objman.Sqhlhan.get_conn(read_only=False)

		suc_start = self.start()

		# clear after successfully finished start()
		self.core_terminated_event.clear()

		# pathfinding should be a method/function, not a thread

		# setup Events to signal quitting
		trade_logic_event = threading.Event()
		contract_logic_event = threading.Event()
		actionfinder_logic_event = threading.Event()
		marketdata_logic_event = threading.Event()

		self.main_thr_events.append(self.logic_event)
		self.main_thr_events.append(trade_logic_event)
		self.main_thr_events.append(contract_logic_event)
		self.main_thr_events.append(actionfinder_logic_event)
		self.main_thr_events.append(marketdata_logic_event)

		# setup logic threads
		self.core_thr_events.append(trade_logic_event)
		self.core_thr_events.append(contract_logic_event)
		self.core_thr_events.append(actionfinder_logic_event)
		self.core_thr_events.append(marketdata_logic_event)

		# PreTasks_list is the list in Class PreTask: PT_list 

		# only if start was successfull
		if suc_start in (None, True):
			Shps = Ships(self.ShipHandlers)

			# contract
			ctrct_logi = ContractLogic(self.Objman, contract_logic_event)
			self.core_threads.append(ctrct_logi.thr)

			# Marketdata
			Mrkt = Market(self.Objman)
			mrktd_logi = MarketdataLogic(self.Objman, Mrkt, Shps, marketdata_logic_event)
			self.core_threads.append(mrktd_logi.thr)

			# ActionFinder
			actf_Q = queue.Queue()
			actf_logi = ActionFinder(self.Objman, Shps, Mrkt, self.ShipHandlers, actf_Q, actionfinder_logic_event)
			self.core_threads.append(actf_logi.thr)

		self.__class__._log.info("[t_core] instantiated with id %(threadID)s", {"threadID": threading.get_ident(), "_msg_args": ["arg", "value"]})

		
		
		# TODO:
		# make Task Object, implement tasks table in scheme.ex...
		# go with pandas for calc_hoops in Task

		# start main logic loop
		while not self.logic_event.is_set() and not self.Objman.is_fresh_reset:


			time.sleep(1)

		


		# close thread Connections
		# close open DB connections
		if not self.Objman.Sqhlhan.ConnHandler.remove_thr_conns():
			self.__class__._log.error(f"core failed closing all thread Connections to DB {short(self.Objman.Sqhlhan.dbfp)}")

		# remove t_core's threads from main_thr_events list
		for ev in self.core_thr_events:
			self.main_thr_events.remove(ev)
			ev.set()

		# set this to indicate to Objman that it can clear logic_event
		# this thread t_core know it just needs to restart, not end
		self.core_terminated_event.set()
		time.sleep(1)

		self.core_thr_events.clear()

		for t in self.core_threads:
			# in case of is_fresh_reset one thread will most likely
			# burn through timeout, since it is a deadlock between this
			# join and it's wait to get signal 
			t.join(self.Objman.Conf.config["THREAD_CORE_JOIN_TIMEOUT"])

			if t.is_alive():
				self.__class__._log.error(f"thread '{t.name}' failed to self-close")
				# TODO collect all zombie threads in a list

			# don't remove own thread from main_threads list
			if t in self.main_threads and t.name != "t_core":
				self.main_threads.remove(t)
		
		if self.Objman.is_fresh_reset:
			time.sleep(10)
			# need to restart
			self.core()
		else:
			self.__class__._log.info(f"[t_core] closed")


	def start(self) -> bool:
		# flag to indicate if self.fresh_start_procedure() needs to run
		run_fresh_start = False
		
		# run register_new_agent if Objman has flag set
		if self.Objman.is_fresh_reset:
			# also sets Objman.Agent if successful
			if self.register_new_agent(): # could return more values: suc, re_dec # then give ShipHandler ships data
				self.Objman.is_fresh_reset = False
				run_fresh_start = True

		else:
			self.Objman.Agent = Agent(self.Objman)

		# self.Objman.Agent.data should be set by Agent __init__ only when
		# is_fresh_start from Objman indicates it
		if None in (self.Objman.Agent.data, self.Objman.Agent):
			return False

		ShipH = ShipHandler(self.Objman, fleet_name="1", agent_total=self.Objman.Agent.shipCount)
		self.ShipHandlers.update({ShipH.fleet: ShipH})

		self.systems = {ShipH.fleet_sys: Waypoint.api_get_all_sys_wp(self.Objman, ShipH.fleet_sys)}

		if run_fresh_start:
			self.fresh_start_procedure()

		return True


	def fresh_start_procedure(self):
		# 1. accept contract

		# 2. go to ENGINEERED_ASTEROID with main ship and extract

		pass


	def register_new_agent(self, attempt:int=0) -> bool:
		url, data = self.Objman.Conf.config["sites"]["SPACETRADERS"]["POST"]["REGISTER"]
		# get random predefined callsign & faction
		data.update({
			"symbol": "ASIDE_"+self.Objman.Conf.config["CALLSIGN_SUFX"][random.randint(0, len(self.Objman.Conf.config["CALLSIGN_SUFX"])-1)],
			"faction": self.Objman.Conf.config["FACTIONS"][random.randint(0, len(self.Objman.Conf.config["FACTIONS"])-1)]
		})
		
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
		bearer.update({"AGENT": {"Authorization": "Bearer "+re_dec["data"]["token"].strip()}})
		# save new bearer
		if not jsonf.save(bearer, ".env"):
			self.__class__._log.error("register_new_agent failed saving new token in .env")

		self.Objman.Netwsess.set_auth_header(header=bearer["AGENT"], host="spacetraders.io")

		# new HQ of own faction
		headq_val = {
						"factions": re_dec["data"]["faction"]["symbol"],
						"waypoints_id": None,		# only have system
						"systemsymbol": re_dec["data"]["faction"]["headquarters"],
						"updated": int(time.time())
		}

		# insert
		if not self.Objman.ins("headq", list(headq_val.values())):
			self.__class__._log.error(f"register_new_agent failed inserting new headq {headq_val}")

			return False

		# set Agent from data received by registration
		self.Objman.Agent = Agent(self, data=re_dec["data"]["agent"])
		# for some reason shipCount is probably set to 0
		# so need to change that for ShipHandler to work
		if self.Objman.Agent.data["shipCount"] == 0:
			self.Objman.Agent.data["shipCount"] = 2
		
		return True
