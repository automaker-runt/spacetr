# tasks
import time, copy, random, logging
import threading
from typing import Union

from core.ships import Ship
from core.utils import dfop
from core.utils.coord import GameCoord, distance
from core.utils.marketdata import cycle
from core.navigation import Navigation
from core.utils.objmanager import ObjManager
from core.waypoints import Waypoint
from hkeep.error import tb
from hkeep.log.logger import get_logger
from utils.strings.shorten import short
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
						prio: Union[int, None]=None,
						liberty_on_done:bool=True):
		
		PT.ship.has_task = True
		PT.ship.task_id = PT.id_
		PT.ship._update_state()
		self.PT = PT
		self.Mrkt = Mrkt
		self.prio = prio if prio is not None else PT.prio
		self.liberty_on_done = liberty_on_done

		if self not in self.__class__.T_list:
			self.__class__.T_list.append(self)

		# PT.schedule?

		self.ev_quit = threading.Event()
		self.thr = threading.Thread(target=self.work, name=f't_{self.tsk_type[0].upper()}Tsk_{self.id_[-5:]}', daemon=True)
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
		# inheritance
		# find out the type of PT, take according measures
		pass


	def end_work(self, finished:bool):
		if self.liberty_on_done:	
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


	def hop_in_range(self, distance_to_target: float, mode:str="CRUISE", current_fuel: Union[int, None]=None) -> bool:
		"""
		Determines if ship should refuel based on distance and current fuel
		"""
		if current_fuel is None:
			current_fuel = self.ship.fuel

		if mode in ("CRUISE", "STEALTH"):
			fuel_needed = round(distance_to_target)

		elif mode == "DRIFT":
			fuel_needed = 1

		elif mode == "BURN":
			amt = 2*round(distance_to_target)
			fuel_needed = max(2, amt)
		
		# return whether hop is in range
		return current_fuel >= fuel_needed
	
	
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

		url = copy.deepcopy(self.Objman.Conf.config["sites"]["SPACETRADERS"]["GET"]["SHIPYARD_DATA"])
		url = url.format(systemSymbol=self.sys, WaypointSymbol=self.ship.waypoint)
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

		url = copy.deepcopy(self.Objman.Conf.config["sites"]["SPACETRADERS"]["GET"]["MARKETPLACE_DATA"])
		url = url.format(systemSymbol=self.sys, WaypointSymbol=self.ship.waypoint)
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
		# - ev_quit is set
		if "cooldown" in jj and "expiration" in jj["cooldown"]:
			wait(ISO_to_epoch(jj["cooldown"]["expiration"]), interval=1.0, ev_quit=self.ev_quit)

		# only wait for arrival if ship.status is not DOCKED
		if self.ship.status != "DOCKED" and "nav" in jj and "route" in jj["nav"]:
			wait(ISO_to_epoch(jj["nav"]["route"]["arrival"]), interval=1.0, ev_quit=self.ev_quit)
			if self.go:
				self.ship.jj["nav"]["status"] = "IN_ORBIT"
				self.ship._update_state()


	def calculate_furthest_hop(self, start_coord:GameCoord, target_coord:GameCoord, mode:str) -> GameCoord:
		"""
		Calculates the furthest possible waypoint in the direction of the target
		that can be reached with current fuel levels
		"""
		# Get refuelable waypoints
		direction_wps = dfop.wp_type_traits_lookup(self.df_sys_wps, ["FUEL_STATION"], ["MARKETPLACE"])
		
		current_dist = distance(start_coord, target_coord)
		# Filter to only waypoints closer to target than current position
		closer_wps = direction_wps[direction_wps.apply(lambda x: 
			distance(x.GmCrd, target_coord) < current_dist, axis=1)]
		
		# Find furthest reachable waypoint
		reachable = closer_wps[closer_wps.apply(lambda x: 
										self.ship.in_range(x.GmCrd, mode=mode, reserve=0.01), axis=1)]
			
		if len(reachable) > 0:
			return dfop.furthest(reachable, target_coord)
			
		return None
	
	
	def follow_path(self, coord:GameCoord) -> bool:
		'''
		Creates and follows a path of waypoints
		'''
		# omegalul Navigation Class by AI
		Nav = Navigation(self.Objman, self.df_sys_wps, self.Mrkt.df)
		path, est_total_cost, refuel_cost = Nav.optimize_route(self.ship.coordinates,
											coord,
											self.ship.fuel,
											self.ship.fuelCapacity,
											self.flight_mode)
		if not path:
			self.__class__._log.warning(f"[{self.thr.name}] follow_path returned no path from {str(self.ship.coordinates)} to {str(coord)} {str(self)}")

			return False
		
		print()
		print(f"[{self.thr.name}] {str(self.ship)} on path with {len(path)} hops with planned fuel cost µ{refuel_cost} and total cost {est_total_cost}")
		print(f"[{self.thr.name}] {str(self.ship)} {len(path)} hops : {list((str(i['coord']), i['refuel'], i['refuel_amount'], i['mode']) for i in path if 'coord' in i)}")

		return True
		
		for wp in path:
			self.check_markets()

			if not self.ship.go_waypoint(coord=wp["coord"], mode=self.flight_mode, dwnti_func=self.shp_dwnti_func):
				return False
			
			if wp["refuel"]:
				payed, suc = self.ship.refuel(amount=wp["refuel_amount"], dwnti_func=self.shp_dwnti_func)
				if not suc:
					return False
				cost += payed

		if est_total_cost != 0:
			self.__class__._log.info(f"[{self.thr.name}] {str(self.ship)} followed path to {str(path[-1]['coord'])} costing µ{cost} (planned µ{est_total_cost})")
		else:
			self.__class__._log.info(f"[{self.thr.name}] {str(self.ship)} followed path to {str(path[-1]['coord'])} costing µ{cost}")

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


	def deliver(self) -> bool:
		# go with ship to the deliver waypoint
		if not self.follow_path(self.GmCrd_dict["deliver"]):			
			self.__class__._log.error(f"[{self.thr.name}] deliver failed to find path {str(self)}")
			
			return False
		
		# dock ship
		if not self.ship.go_dock():
			self.__class__._log.error("deliver failed go_dock at '{}'".format(str(self.GmCrd_dict["deliver"])))

			return False

		self.shp_dwnti_func(self.ship.jj)

		# deliver good
		url, data = copy.deepcopy(self.Objman.Conf.config["sites"]["SPACETRADERS"]["POST"]["DELIVER_CONTRACT"])
		url = url.format(contractId=self.tsk_item.sptr_id)
		data.update({	
						"shipSymbol": self.ship.name,
						"tradeSymbol": self.extras["good"]["tradeSymbol"],
						"units": next(i["units"] for i in self.ship.cargoInv if i["symbol"] == self.extras["good"]["tradeSymbol"])
						})

		suc, re = self.Objman.post(url=url, data=data)

		if not suc:
			self.__class__._log.error("deliver failed to deliver {} {} at '{}'".format(data["units"], data["tradeSymbol"], str(self.GmCrd_dict["deliver"])))

			return False

		re_dec = re.Response.json()

		# update the contract details and ship cargo
		self.extras["good"] = re_dec["data"]["contract"]["terms"]["deliver"][0]
		old_ctrct_data = copy.deepcopy(self.tsk_item.ctrct_data)
		self.tsk_item.ctrct_data = re_dec["data"]["contract"].copy()
		self.tsk_item.update_contract(DB_state=old_ctrct_data)
		self.ship.jj["cargo"] = re_dec["data"]["cargo"]
		self.ship._update_state()

		self.shp_dwnti_func(self.ship.jj)

		return True
	

	def work(self):

		self.__class__._log.info("[{}] instantiated with id %(threadID)s".format(self.thr.name), {"threadID": threading.get_ident(), "_msg_args": ["arg", "value"]})

		# wait for the ship to be ready to receive commands
		self.shp_dwnti_func(self.ship.jj)

		finished = False

		while self.go and not finished:
			start_ti = int(time.time())

			self.check_markets()
						
			# go deliver if done
			if self.go and self.ctrct_fulf:
				assert self.deliver(), f"Error deliver {str(self)}"
				finished = True

			# if ship has full cargo, decide what to do with it
			if self.go and self.inv_full:
				pass
				# either or combination of
				# go to marketplace and sell, if near delivery wp -> go and deliver if it is a great chunk of storage already
				# jettison

				# if going to deliver self.extras["good"] needs to be updated

			# if ship is where it is supposed to mine
			# mine (aka extract)
			if self.go and self.ship.waypoint == self.GmCrd_dict["mine"].wp:
				assert self.ship.extract_ores(dwnti_func=self.shp_dwnti_func), f"Error ship.extract_ores {str(self)}"

			# if ship is not where it is mining, move it there
			elif self.go and self.ship.waypoint != self.GmCrd_dict["mine"].wp:
				""" print()
				for _, wp in self.df_sys_wps.drop_duplicates(subset=["coords"]).iterrows():
					if not self.go:
						break
					if wp["wp_symbol"] == self.ship.waypoint:
						continue

					to = wp["GmCrd"]
					print("going for path to", to)
					# Navigation._log.setLevel(logging.DEBUG)
					# assert self.follow_path(to), f"Error follow_path {str(self)}"
					print(f"pathing finished {self.follow_path(to)}")
					time.sleep(1)
				print("Done") """
				
				while self.go:
					time.sleep(1)

				assert self.follow_path(self.GmCrd_dict["mine"]), f"Error follow_path {str(self)}"

			# make wait if nothing happened (for some reason -> ?)
			if self.go and start_ti+int(self.Objman.Conf.config["THREAD_TASK_INTERVAL"]) > int(time.time()):
				time.sleep(self.Objman.Conf.config["THREAD_TASK_INTERVAL"])

		# realease ship
		self.end_work(finished)


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
				break
						
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
		self.end_work(finished)
