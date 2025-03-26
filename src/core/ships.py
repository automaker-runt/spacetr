# ships
import time, math, copy
import threading
import pandas as pd
from collections import Counter
from functools import partial
from typing import Union

from core.utils import coord, meta, netw
from core.utils.objmanager import ObjManager
from core.waypoints import Waypoint
from hkeep.log.logger import get_logger
from utils.list import create
from utils.sql import strings
from utils.strings.shorten import short
from utils.time import ISO_to_epoch, conv_time_time_to_def


class Ship:

	_log = get_logger(__name__)
	inventory = dict()

	@classmethod
	def get_ship_id(cls, Objman, ship_sym:str) -> Union[int, None]:
		re = Objman.sel(f"SELECT id FROM ships WHERE symbol=?;", (ship_sym,), _format=False)

		if len(re) > 0:

			return re[0][0]

		else:
			return


	@classmethod
	def _get_ship_main_info_col_blueprint(cls) -> dict:
		blueprint =	{
							"symbol": None,
							"systemsymbol": None,
							"waypoints_id": None,
							"origin_wp_id": None,
							"destination_wp_id": None,
							"arrival": None,
							"departure": None,
							"status": None,
							"flightMode": None,
							"crew_curr": None,
							"crew_capa": None,
							"crew_requ": None,
							"crew_rotation": None,
							"crew_morale": None,
							"crew_wages": None,
							"fuel_curr": None,
							"fuel_capa": None,
							"fuel_cons_amt": None,
							"fuel_cons_time": None,
							"cd_shipsym": None,	# watch if it differs ever from "symbol"
							"cd_secs": None,
							"cd_expiration": None,
							"frame": None,
							"frame_condition": None,
							"frame_integrity": None,
							"reactor": None,
							"reactor_condition": None,
							"reactor_integrity": None,
							"engine": None,
							"engine_condition": None,
							"engine_integrity": None,
							"reg_name": None,
							"reg_faction": None,
							"reg_role": None,
							"cargo_capa": None,
							"cargo_units": None,
							"fleets_id": None,
							"updated": None
			}

		return blueprint


	def __init__(self, jj:dict, sdf:list, Objman:ObjManager, fleet:str):
		self.jj = jj
		self.sdf = sdf # is list containig pd.core.frame.DataFrame at idx 0
		self.Objman = Objman
		self.jj2 = {
					"fleet": fleet,
					"ship_id": None,
					"has_task": False,
					"task_id": None
		}

		self.get_wp_id = partial(Waypoint.get_wp_id, Objman)
		self.get_wp_sym = partial(Waypoint.get_wp_sym, Objman)
		self.insert_wp = partial(Waypoint.insert_wp, Objman)
		self.get_ship_id = partial(self.__class__.get_ship_id, Objman)
		
		

		# if read ship symbol through DB, need to load the rest
		if self.jj["frame"] is None:
			self.jj = self.select_ship()		
		
		self.prev_jj = copy.deepcopy(self.jj)
		self.prev_jj2 = copy.deepcopy(self.jj2)
		# update sdf
		self.updt_sdf()

		self.__class__._log.info(f"new ship '{self.name}.{self.frame.lower()}' added to fleet '{fleet}'")

		# manage loaded status "IN_TRANSIT"
		if self.status == "IN_TRANSIT":
			
			def put_status_in_orbit(waiter: Union[None, float]=None):
				if waiter is not None:
					time.sleep(waiter)

				self.jj["nav"]["status"] = "IN_ORBIT"
				self._update_state()

				# when executed as thread with waiter not None, close DB connection
				if waiter is not None and not self.Objman.Sqhlhan.ConnHandler.remove_thr_conns():
					self.__class__._log.error(f"failed to remove thread connections to DB {short(self.Objman.Sqhlhan.dbfp)}")
			
			# can change it right now
			if ISO_to_epoch(self.arrival) <= time.time():
				put_status_in_orbit()
			
			# can't change it right now, wait via threading.Timer
			else:
				threading.Thread(target=put_status_in_orbit, args=(ISO_to_epoch(self.arrival) - time.time(),), daemon=True).start()
	
	
	def __str__(self) -> str:
		return f"{self.name}.{self.frame.lower()}"


	@property
	def task_id(self) -> str:
		return self.jj2["task_id"]

	@task_id.setter
	def task_id(self, value):
		self.jj2["task_id"] = value

	@property
	def has_task(self) -> str:
		return self.jj2["has_task"]

	@has_task.setter
	def has_task(self, value):
		self.jj2["has_task"] = value

	@property
	def fleet(self) -> str:
		return self.jj2["fleet"]

	@fleet.setter
	def fleet(self, value):
		self.jj2["fleet"] = value

	@property
	def name(self) -> str:
		return self.jj["symbol"]

	@property
	def ship_id(self) -> str:
		if self.jj2["ship_id"] is None:
			self.jj2["ship_id"] =  self.__class__.get_ship_id(self.Objman, self.name)
		return self.jj2["ship_id"]

	@property
	def goods_in_cargoInv(self) -> str:
		return list(i["symbol"] for i in self.cargoInv)

	@property
	def frame(self) -> int:
		if self.jj["frame"] is not None:
			return self.jj["frame"]["name"]
		else:
			return "unknown"

	@property
	def role(self) -> int:
		return self.jj["registration"]["role"]

	@property
	def status(self) -> str:
		return self.jj["nav"]["status"]

	@property
	def cooldown_exp(self) -> int:
		if ("expiration" in self.jj["cooldown"] and
			self.jj["cooldown"]["expiration"] != 0 and
			isinstance(self.jj["cooldown"]["expiration"], str)):
			return int(ISO_to_epoch(self.jj["cooldown"]["expiration"]))
		else:
			return 0

	@property
	def arrival(self) -> int:
		return self.jj["nav"]["route"]["arrival"]

	@property
	def fuel(self) -> int:
		return self.jj["fuel"]["current"]

	@property
	def fuelCapacity(self) -> int:
		return self.jj["fuel"]["capacity"]

	@property
	def flightMode(self) -> str:
		return self.jj["nav"]["flightMode"]

	@property
	def coordinates(self) -> coord.GameCoord:
		return coord.GameCoord(int(self.jj["nav"]["route"]["destination"]["x"]),
								int(self.jj["nav"]["route"]["destination"]["y"]),
								self.jj["nav"]["route"]["destination"]["symbol"])

	@property
	def waypoint(self) -> int:
		return self.jj["nav"]["waypointSymbol"]

	@property
	def system(self) -> int:
		return self.jj["nav"]["systemSymbol"]

	@property
	def engineSpeed(self) -> int:
		return self.jj["engine"]["speed"]

	@property
	def cargoInv(self) -> int:
		return self.jj["cargo"]["inventory"]

	@property
	def cargoCapa(self) -> int:
		return self.jj["cargo"]["capacity"]

	@property
	def cargoUnits(self) -> int:
		return self.jj["cargo"]["units"]


	def _update_state(self, inp: Union[dict, None]=None):
		"""
		Updates the ship's state in memory and database.
		
		When called without arguments:
		- Compares current state (jj, jj2) with previous state (prev_jj, prev_jj2)
		- If different, updates the database with current state
		
		When called with inp argument:
		- Updates the ship's state (jj) with the provided input
		- Updates the database with the new state
		
		In all cases, updates the DataFrame representation via updt_sdf()
		"""
		if inp is None:
			# No input provided - check if current state differs from previous state
			sdf_update_needed = False
			
			# Check if main ship data changed
			if self.jj != self.prev_jj:
				# Update database with current state, providing DB_state as argument
				self.update_ship(self.prev_jj)
				# Store current state as previous state
				self.prev_jj = copy.deepcopy(self.jj)
				sdf_update_needed = True
				
			# Check if secondary ship data changed
			if self.jj2 != self.prev_jj2:
				self.prev_jj2 = copy.deepcopy(self.jj2)
				sdf_update_needed = True
		else:
			sdf_update_needed = False
			# Input provided - update ship state with input
			DB_state = copy.deepcopy(self.jj)
			self.jj.update(inp)
			
			# Update database if state changed
			if DB_state != self.jj:
				sdf_update_needed = True
				self.update_ship(DB_state)
				
			# Store current state as previous state
			self.prev_jj = copy.deepcopy(self.jj)
			self.prev_jj2 = copy.deepcopy(self.jj2)
		
		# Update the DataFrame representation
		if sdf_update_needed:
			self.updt_sdf()


	def fuel_cost(self, coord:coord.GameCoord, mode:str="CRUISE", coord_b: Union[coord.GameCoord, None]=None) -> int:
		if coord_b is None:
			coord_b = self.coordinates

		dist = coord.distance(coord_b, coord)

		if mode in ("CRUISE", "STEALTH"):
			return round(dist)

		elif mode == "DRIFT":
			return 1

		elif mode == "BURN":
			amt = 2*round(dist)
			return max(2, amt)


	def travel_time(self, coord:coord.GameCoord, mode:str="CRUISE", coord_b: Union[coord.GameCoord, None]=None) -> int:
		if coord_b is None:
			coord_b = self.coordinates

		multiplier = self.Objman.Conf.config["NAVIGATION_MULTIPLIER"][mode]
		
		return round(round(max(1, coord.distance(coord_b, coord))) * (multiplier / self.engineSpeed) + 15)


	def in_range(self, coord:coord.GameCoord,
						mode:str="CRUISE",
						current_fuel: Union[int, None]=None,
						reserve: Union[int, float]=0.05,
						coord_b: Union[coord.GameCoord, None]=None) -> bool:

		if coord_b is None:
			coord_b = self.coordinates

		# if it's a probe, it is always in range, since no fuel cost
		if self.frame == "Probe":
			return True

		else:
			f_cost = self.fuel_cost(coord, mode=mode, coord_b=coord_b)
			if current_fuel is None:
				current_fuel = self.fuel
			
			# adding default 5% reserve to have left
			# for theory reasons, sometimes calculate with different reserve
			if float(current_fuel - f_cost) >= self.fuelCapacity*reserve:
				return True
			else:
				return False


	def go_waypoint(self, coord:coord.GameCoord, mode:str="CRUISE", reserve:float=0.05, dwnti_func=None) -> bool:
		
		if not self.in_range(coord, mode=mode, reserve=reserve):
			self.__class__._log.error(f"go_waypoint {self.name}.{self.frame.lower()} to {coord} failed because ship is out of range")

			return False

		# we have enough fuel to go to coord

		# check if we are in orbit, if not, go there
		if self.status != "IN_ORBIT":
			if not self.go_orbit():
				self.__class__._log.error(f"go_waypoint {str(self)} to {str(coord)} failed because ship failed going to orbit first")

				return False

			if dwnti_func:
				dwnti_func(self.jj)

		# we are in orbit and can go now
		url, data = copy.deepcopy(self.Objman.Conf.config["sites"]["SPACETRADERS"]["POST"]["GO_WAYPOINT"])

		url = url.format(ShipSymbol=self.name)
		data.update({"waypointSymbol": coord.wp})

		suc, re = self.Objman.post(url=url, data=data)

		if not suc:
			self.__class__._log.error(f"go_waypoint {str(self)} to {str(coord)} failed ({re.Response._reqID})")

			return False		

		# need to update Ship state in self.jj
		self._update_state(re.Response.json()["data"])

		if dwnti_func:
			self.__class__._log.info(f"[{threading.current_thread().name}] {str(self)} on the way to {str(coord)}")
			dwnti_func(self.jj)
			
		else:
			self.__class__._log.info(f"{str(self)} on the way to {str(coord)}")

		# need to patch flightMode
		if self.flightMode != mode:
			# TODO send patch request
			self.__class__._log.error(f"go_waypoint detected needed change in flight mode for {str(self)} on the way to {str(coord)} but it isn't implemented")
		
		return True
			


	def go_orbit(self) -> bool:
		url = copy.deepcopy(self.Objman.Conf.config["sites"]["SPACETRADERS"]["POST"]["GO_ORBIT"])

		url = url.format(ShipSymbol=self.name)

		suc, re = self.Objman.post(url=url, data=dict())

		if not suc:
			self.__class__._log.error(f"go_orbit {self.name}.{self.frame.lower()} failed to orbit at {str(self.coordinates)} ({re.Response._reqID})")

			return False

		re_dec = re.Response.json()

		self.__class__._log.info(f"{self.name}.{self.frame.lower()} went to orbit {str(self.coordinates)}")
		
		# need to update Ship state in self.jj
		self._update_state(re_dec["data"])
		
		return True


	def go_dock(self) -> bool:
		url = copy.deepcopy(self.Objman.Conf.config["sites"]["SPACETRADERS"]["POST"]["DOCK_SHIP"])

		url = url.format(ShipSymbol=self.name)

		suc, re = self.Objman.post(url=url, data=dict())

		if not suc:
			self.__class__._log.error(f"go_dock {self.name}.{self.frame.lower()} failed to dock at {str(self.coordinates)} ({re.Response._reqID})")

			return False

		self.__class__._log.info(f"{self.name}.{self.frame.lower()} went to dock {str(self.coordinates)}")
		
		# need to update Ship state in self.jj
		self._update_state(re.Response.json()["data"])
		
		return True			


	def extract_ores(self, dwnti_func=None) -> bool:
		# check if we are in orbit, if not, go there
		if self.status != "IN_ORBIT":
			if not self.go_orbit():	
				self.__class__._log.error(f"extract_ores {self.name}.{self.frame.lower()} from {str(self.coordinates)} failed because ship failed going to orbit first")

				return False

			if dwnti_func:
				dwnti_func(self.jj)

		# we are in orbit, we can extract now
		url = copy.deepcopy(self.Objman.Conf.config["sites"]["SPACETRADERS"]["POST"]["EXTRACT_ORES"])

		url = url.format(miningShipSymbol=self.name)

		suc, re = self.Objman.post(url=url, data=dict())

		if not suc:
			self.__class__._log.error(f"extract_ores {self.name}.{self.frame.lower()} failed to start extracting ores at {str(self.coordinates)} ({re.Response._reqID})")

			return False
		
		# need to update Ship state in self.jj
		re_dec = re.Response.json()
		self.jj["cooldown"] = re_dec["data"]["cooldown"]
		self.jj["cargo"] = re_dec["data"]["cargo"]
		self._update_state()

		if dwnti_func:
			self.__class__._log.info("[{}] {} extracted {} {} at {}".format(threading.current_thread().name,
																			str(self),
																			re_dec["data"]["extraction"]["yield"]["units"],
																			re_dec["data"]["extraction"]["yield"]["symbol"],
																			str(self.coordinates)))
			dwnti_func(self.jj)
		else:
			self.__class__._log.info(f"{str(self)} extracted ores at {str(self.coordinates)}")
		
		return True	


	def refuel(self, amount:int=0, dwnti_func=None) -> tuple[int, bool]:
		# one unit at MARKETPLACE replenishes 100 units in ship tank
		if amount == 0:
			url = copy.deepcopy(self.Objman.Conf.config["sites"]["SPACETRADERS"]["POST"]["REFUEL"])
			data = dict()
		else:
			amount = math.ceil(amount/100)			
			url, data = copy.deepcopy(self.Objman.Conf.config["sites"]["SPACETRADERS"]["POST"]["REFUEL_AMT"])
			data.update({"units": amount, "fromCargo": False})

		url = url.format(ShipSymbol=self.name)

		suc, re = self.Objman.post(url=url, data=data)

		if not suc:
			self.__class__._log.error(f"refuel {str(self)} at {str(self.coordinates)} ({re.Response._reqID})")

			return 0, False
		
		re_dec = re.Response.json()
		
		# need to update Ship state in self.jj
		self._update_state({"fuel": re_dec["data"]["fuel"]})

		if dwnti_func:
			self.__class__._log.info(f"[{threading.current_thread().name}] {str(self)} refueled at {str(self.coordinates)}")
			dwnti_func(self.jj)
		else:
			self.__class__._log.info(f"{str(self)} refueled at {str(self.coordinates)}")
		
		return re_dec["data"]["transaction"]["totalPrice"], True


	def sell_good(self, good:str, quantity:int) -> bool:
		url, data = copy.deepcopy(self.Objman.Conf.config["sites"]["SPACETRADERS"]["POST"]["SELL"])

		url = url.format(ShipSymbol=self.name)
		data.update({"symbol": good, "units": str(quantity)})
		
		suc, re = self.Objman.post(url=url, data=data)

		if suc:
			self.__class__._log.info(f"{self.name}.{self.frame.lower()} sold {quantity} {good} at {self.waypoint} market")

			return True

		else:
			self.__class__._log.error(f"{self.name}.{self.frame.lower()} failed selling {quantity} {good} at {self.coordinates} market ({re.Response._reqID})")

			return False


	# TODO 
	# implement waypoint scanning
	# using the survey from scanning to extract


	def insert_ship(self, ship_data:dict) -> bool:
		
		# check if ship symbol already in DB
		if self.get_ship_id(ship_data["symbol"]) is None:

			extras = {
									"_frame": {
													"name": ship_data["frame"]["name"],
													"description": ship_data["frame"]["description"],
													"moduleSlots": ship_data["frame"]["moduleSlots"],
													"mountPoints": ship_data["frame"]["mountingPoints"],
													"fuelCapa": ship_data["frame"]["fuelCapacity"],
													"reqi_power": ship_data["frame"]["requirements"]["power"],
													"reqi_crew": ship_data["frame"]["requirements"]["crew"],
													"updated": int(time.time())
									}
			}

			extras.update({
							"_reactor": {
											"name": ship_data["reactor"]["name"],
											"description": ship_data["reactor"]["description"],
											"power_output": ship_data["reactor"]["powerOutput"],
											"reqi_crew": ship_data["reactor"]["requirements"]["crew"],
											"updated": int(time.time())
							}
				})
			extras.update({
							"_engine": {
											"name": ship_data["engine"]["name"],
											"description": ship_data["engine"]["description"],
											"speed": ship_data["engine"]["speed"],
											"reqi_power": ship_data["engine"]["requirements"]["power"],
											"reqi_crew": ship_data["engine"]["requirements"]["crew"],
											"updated": int(time.time())
							}
				})

			if "expiration" in ship_data["cooldown"] and isinstance(ship_data["cooldown"]["expiration"], str):
				cd_exp = ISO_to_epoch(ship_data["cooldown"]["expiration"])
			elif "expiration" in ship_data["cooldown"] and isinstance(ship_data["cooldown"]["expiration"], Union[float, int]):
				cd_exp = ship_data["cooldown"]["expiration"]
			else:
				cd_exp = 0

			sptr_ship = {
							"symbol": ship_data["symbol"],
							"systemsymbol": ship_data["nav"]["systemSymbol"],
							"waypoints_id": self.get_wp_id(ship_data["nav"]["waypointSymbol"]),
							"origin_wp_id": self.get_wp_id(ship_data["nav"]["route"]["origin"]["symbol"]),
							"destination_wp_id": self.get_wp_id(ship_data["nav"]["route"]["destination"]["symbol"]),
							"arrival": ISO_to_epoch(ship_data["nav"]["route"]["arrival"]),
							"departure": ISO_to_epoch(ship_data["nav"]["route"]["departureTime"]),
							"status": ship_data["nav"]["status"],
							"flightMode": ship_data["nav"]["flightMode"],
							"crew_curr": ship_data["crew"]["current"],
							"crew_capa": ship_data["crew"]["capacity"],
							"crew_requ": ship_data["crew"]["required"],
							"crew_rotation": ship_data["crew"]["rotation"],
							"crew_morale": ship_data["crew"]["morale"],
							"crew_wages": ship_data["crew"]["wages"],
							"fuel_curr": ship_data["fuel"]["current"],
							"fuel_capa": ship_data["fuel"]["capacity"],
							"fuel_cons_amt": ship_data["fuel"]["consumed"]["amount"],
							"fuel_cons_time": ISO_to_epoch(ship_data["fuel"]["consumed"]["timestamp"]),
							"cd_shipsym": ship_data["cooldown"]["shipSymbol"],	# watch if it differs ever from "symbol"
							"cd_secs": ship_data["cooldown"]["totalSeconds"],
							"cd_expiration": cd_exp,
							"frame": ship_data["frame"]["symbol"],
							"frame_condition": ship_data["frame"]["condition"],
							"frame_integrity": ship_data["frame"]["integrity"],
							"reactor": ship_data["reactor"]["symbol"],
							"reactor_condition": ship_data["reactor"]["condition"],
							"reactor_integrity": ship_data["reactor"]["integrity"],
							"engine": ship_data["engine"]["symbol"],
							"engine_condition": ship_data["engine"]["condition"],
							"engine_integrity": ship_data["engine"]["integrity"],
							"reg_name": ship_data["registration"]["name"],
							"reg_faction": ship_data["registration"]["factionSymbol"],
							"reg_role": ship_data["registration"]["role"],
							"cargo_capa": ship_data["cargo"]["capacity"],
							"cargo_units": ship_data["cargo"]["units"],
							"fleets_id": self.fleet,
							"updated": int(time.time())
			}

			if self.Objman.ins("ships", list(sptr_ship.values()), extras=extras):
				# get the ship id
				ship_id = self.get_ship_id(ship_data["symbol"])

				# need to go further with tables for modules, mounts

				error = False

				if len(ship_data["modules"]) > 0:
					if not self.insert_ship_modules(ship_data["modules"], ship_id):
						error = True
				if len(ship_data["mounts"]) > 0:
					if not self.insert_ship_mounts(ship_data["mounts"], ship_id):
						error = True

				if len(ship_data["cargo"]["inventory"]) > 0:
					if not self.insert_cargo(ship_data["cargo"]["inventory"], ship_id):
						error = True

				if not error:
					self.__class__._log.info("new ship '{}.{}' added".format(ship_data["symbol"], ship_data["frame"]["symbol"].lower()))
					return True
				else:
					self.__class__._log.error("insert_ships failed inserting modules or mounts after creating new ship '{}'".format(ship_data["symbol"]))
					return False

			else:
				self.__class__._log.error("insert_ships failed inserting 'ships' entry for {}".format(ship_data["symbol"]))

				return False

		else:
			self.__class__._log.warning("insert_ships tried inserting already known ship '{}'".format(ship_data["symbol"]))

			return False


	def insert_ship_modules(self, module_data:list, ship_sym_id:int) -> bool:

		for module in module_data:
			# have to reformat requirements to top level
			reqi = module.pop("requirements")
			module.update({
							"reqi_crew": reqi["crew"],
							"reqi_power": reqi["power"],
							"reqi_slots": reqi["slots"]
				})

			com = f"SELECT id FROM modules WHERE symbol=?;"
			com_var = (module["symbol"],)

			re = self.Objman.sel(com, com_var, _format=False)

			if len(re) == 0:
				# append time for updated column
				vals = list(module.values())
				vals.append(int(time.time()))

				# handle case when module doesn't have field
				# capacity
				if "capacity" not in module:
						vals.insert(3, 0)

				if self.Objman.ins("modules", vals):
					self.__class__._log.info("new ship module '{}' added".format(module["symbol"]))

					re = self.Objman.sel(com, com_var, _format=False)
					module_id = re[0][0]

					if not self.Objman.ins("_ship_modules", [ship_sym_id, module_id], no_duplicates=False):
						self.__class__._log.error(f"handle_ship_modules failed insert in '_ship_modules': {[ship_sym_id, module_id]}")
						
						return False

				else:
					self.__class__._log.error(f"handle_ship_modules failed insert in 'modules': {vals}")
					
					return False

			else:
				module_id = re[0][0]

				# com = f"SELECT * FROM _ship_modules WHERE ship_sym_id=? AND modules_id=?;"
				# com_var = (ship_sym_id, module_id)

				# re = self.Objman.sel(com, com_var, _format=False)

				# if len(re) == 0:
				if not self.Objman.ins("_ship_modules", [ship_sym_id, module_id], no_duplicates=False):
					self.__class__._log.error(f"handle_ship_modules failed after module already known insert in '_ship_modules': {[ship_sym_id, module_id]}")
					
					return False

		return True


	def insert_ship_mounts(self, mounts_data:list, ship_sym_id:int) -> bool:

		for mount in mounts_data:
			# have to reformat requirements to top level
			reqi = mount.pop("requirements")
			mount.update({
							"reqi_crew": reqi["crew"],
							"reqi_power": reqi["power"]
				})

			com = f"SELECT id FROM mounts WHERE symbol=?;"
			com_var = (mount["symbol"],)

			re = self.Objman.sel(com, com_var, _format=False)

			if len(re) == 0:				
				# append time for updated column
				vals = list(mount.values())
				vals.append(int(time.time()))

				# handle case when mount doesn't have field
				# deposits
				if "deposits" not in mount:
						vals.insert(4, 0)
				else:
					vals[4] = ', '.join(mount["deposits"])

				if self.Objman.ins("mounts", vals):
					self.__class__._log.info("new ship mount '{}' added".format(mount["symbol"]))

					re = self.Objman.sel(com, com_var, _format=False)
					mount_id = re[0][0]

					if not self.Objman.ins("_ship_mounts", [ship_sym_id, mount_id], no_duplicates=False):
						self.__class__._log.error(f"handle_ship_mounts failed insert in '_ship_mounts': {[ship_sym_id, mount_id]}")

						return False

				else:
					self.__class__._log.error(f"handle_ship_mounts failed insert in 'mounts': {vals}")
					
					return False

			else:
				mount_id = re[0][0]

				# com = f"SELECT * FROM _ship_mounts WHERE ship_sym_id=? AND mounts_id=?;"
				# com_var = (ship_sym_id, mount_id)

				# re = self.Objman.sel(com, com_var, _format=False)

				# if len(re) == 0:
				if not self.Objman.ins("_ship_mounts", [ship_sym_id, mount_id], no_duplicates=False):
					self.__class__._log.error(f"handle_ship_mounts failed after mount already known insert in '_ship_mounts': {[ship_sym_id, mount_id]}")
					
					return False

		return True


	def insert_cargo(self, cargo_inv:list, ship_sym_id: Union[int, None]=None) -> bool:
		# inserts cargo inventory to _ship_cargo

		# set ship_sym_id
		if ship_sym_id is None:
			ship_sym_id = self.ship_id

		for good in cargo_inv:

			# make sure it is known good
			com = f"SELECT id FROM _goods WHERE goods=?;"
			com_var = (good["symbol"],)

			re = self.Objman.sel(com, com_var, _format=False)

			# unknown good needs to be inserted into _goods
			if len(re) == 0:
				# last value is units, which we don't need in goods
				vals = list(good.values())[:-1]
				# adding time for updated column
				vals.append(int(time.time()))

				if not self.Objman.ins("_goods", vals):
					self.__class__._log.error(f"insert_cargo failed insert of new good '{good["symbol"]}'")

					return False

				else:
					self.__class__._log.info("new good '{}' added".format(good["symbol"]))

				re = self.Objman.sel(com, com_var, _format=False)

			# known good needs to be inserted into _ship_cargo
			good_id = re[0][0]

			if not self.Objman.ins("_ship_cargo", [good_id, ship_sym_id, good["units"], int(time.time())]):
				self.__class__._log.error("insert_cargo failed insert in '_ship_cargo': {}".format([good_id, ship_sym_id, good["units"], int(time.time())]))
				
				return False

		return True


	def select_ship(self) -> dict:

		blueprint = self.__class__._get_ship_main_info_col_blueprint()
		# replace reg_faction with factions
		val = blueprint.pop("reg_faction")
		blueprint.update({"factions": val})
		val = blueprint.pop("updated")

		com = f"SELECT {strings.get_str_sql_sel_cols(blueprint)} FROM ships LEFT JOIN _factions ON ships.reg_faction_id = _factions.id WHERE symbol=?;"
		com_var = (self.name,)

		# select ship main info
		re = self.Objman.sel(com, com_var, _format=False)

		if len(re) > 0:
			re = re[0]

			role = re[32]

			ship_data = {}
			ship_data["symbol"] = re[0]
			
			ship_data["nav"] = {}
			ship_data["nav"]["systemSymbol"] = re[1]
			ship_data["nav"]["waypointSymbol"] = self.get_wp_sym(re[2])

			ship_data["nav"]["route"] = {}
			ship_data["nav"]["route"]["origin"] = {}
			ship_data["nav"]["route"]["origin"]["symbol"] = self.get_wp_sym(re[3])
			
			re_ = self.Objman.sel(f"SELECT wp_type, systemsymbol, coords FROM waypoints WHERE wp_symbol=?", (ship_data["nav"]["route"]["origin"]["symbol"],), _format=False)
			if len(re_) > 0:
				ship_data["nav"]["route"]["origin"]["type"] = re_[0][0]
				ship_data["nav"]["route"]["origin"]["systemSymbol"] = re_[0][1]
				if re_[0][2] is not None:
					tup = tuple(re_[0][2].split('::'))
					ship_data["nav"]["route"]["origin"]["x"] = tup[0]
					ship_data["nav"]["route"]["origin"]["y"] = tup[1]
				else:
					ship_data["nav"]["route"]["origin"]["x"] = None
					ship_data["nav"]["route"]["origin"]["y"] = None
			else:
				# should log.error() since
				ship_data["nav"]["route"]["origin"]["type"] = None
				ship_data["nav"]["route"]["origin"]["systemSymbol"] = None
				ship_data["nav"]["route"]["origin"]["x"] = None
				ship_data["nav"]["route"]["origin"]["y"] = None

			ship_data["nav"]["route"]["destination"] = {}
			ship_data["nav"]["route"]["destination"]["symbol"] = self.get_wp_sym(re[4])
			
			re_ = self.Objman.sel(f"SELECT wp_type, systemsymbol, coords FROM waypoints WHERE wp_symbol=?", (ship_data["nav"]["route"]["destination"]["symbol"],), _format=False)
			if len(re_) > 0:
				ship_data["nav"]["route"]["destination"]["type"] = re_[0][0]
				ship_data["nav"]["route"]["destination"]["systemSymbol"] = re_[0][1]
				if re_[0][2] is not None:
					tup = tuple(re_[0][2].split('::'))
					ship_data["nav"]["route"]["destination"]["x"] = tup[0]
					ship_data["nav"]["route"]["destination"]["y"] = tup[1]
				else:
					ship_data["nav"]["route"]["destination"]["x"] = None
					ship_data["nav"]["route"]["destination"]["y"] = None

			else:
				# should log.error() since
				ship_data["nav"]["route"]["destination"]["type"] = None
				ship_data["nav"]["route"]["destination"]["systemSymbol"] = None
				ship_data["nav"]["route"]["destination"]["x"] = None
				ship_data["nav"]["route"]["destination"]["y"] = None
			
			ship_data["nav"]["route"]["arrival"] = conv_time_time_to_def(re[5])
			ship_data["nav"]["route"]["departureTime"] = conv_time_time_to_def(re[6])
			ship_data["nav"]["status"] = re[7]
			ship_data["nav"]["flightMode"] = re[8]

			ship_data["crew"] = {}
			ship_data["crew"]["current"] = re[9]
			ship_data["crew"]["capacity"] = re[10]
			ship_data["crew"]["required"] = re[11]
			ship_data["crew"]["rotation"] = re[12]
			ship_data["crew"]["morale"] = re[13]
			ship_data["crew"]["wages"] = re[14]

			ship_data["fuel"] = {}
			ship_data["fuel"]["current"] = re[15]
			ship_data["fuel"]["capacity"] = re[16]
			
			ship_data["fuel"]["consumed"] = {}
			ship_data["fuel"]["consumed"]["amount"] = re[17]
			ship_data["fuel"]["consumed"]["timestamp"] = conv_time_time_to_def(re[18])

			ship_data["cooldown"] = {}
			ship_data["cooldown"]["shipSymbol"] = re[19]
			ship_data["cooldown"]["totalSeconds"] = re[20]
			ship_data["cooldown"]["expiration"] = conv_time_time_to_def(re[21]) if re[21] != 0 else 0

			ship_data["frame"] = {}
			ship_data["frame"]["symbol"] = re[22]
			
			re_ = self.Objman.sel(f"SELECT name, description, moduleSlots, mountPoints, fuelCapa, reqi_power, reqi_crew FROM _frame WHERE frame=?", (ship_data["frame"]["symbol"],), _format=False)
			if len(re_) > 0:
				ship_data["frame"]["name"] = re_[0][0]
				ship_data["frame"]["description"] = re_[0][1]
				ship_data["frame"]["moduleSlots"] = re_[0][2]
				ship_data["frame"]["mountingPoints"] = re_[0][3]
				ship_data["frame"]["fuelCapacity"] = re_[0][4]
				reqi_power = re_[0][5]
				reqi_crew = re_[0][6]

			else:
				ship_data["frame"]["name"] = None
				ship_data["frame"]["description"] = None
				ship_data["frame"]["moduleSlots"] = None
				ship_data["frame"]["mountingPoints"] = None
				ship_data["frame"]["fuelCapacity"] = None
				reqi_power = None
				reqi_crew = None
			ship_data["frame"]["condition"] = re[23]
			ship_data["frame"]["integrity"] = re[24]

			ship_data["frame"]["requirements"] = {}
			ship_data["frame"]["requirements"]["power"] = reqi_power
			ship_data["frame"]["requirements"]["crew"] = reqi_crew

			ship_data["reactor"] = {}
			ship_data["reactor"]["symbol"] = re[25]

			re_ = self.Objman.sel(f"SELECT name, description, power_output, reqi_crew FROM _reactor WHERE reactor=?", (ship_data["reactor"]["symbol"],), _format=False)
			if len(re_) > 0:
				ship_data["reactor"]["name"] = re_[0][0]
				ship_data["reactor"]["description"] = re_[0][1]
				power_output = re_[0][2]
				reqi_crew = re_[0][3]
			else:
				ship_data["reactor"]["name"] = None
				ship_data["reactor"]["description"] = None
				power_output = None
				reqi_crew = None
			ship_data["reactor"]["condition"] = re[26]
			ship_data["reactor"]["integrity"] = re[27]
			ship_data["reactor"]["powerOutput"] = power_output

			ship_data["reactor"]["requirements"] = {}
			ship_data["reactor"]["requirements"]["crew"] = reqi_crew

			ship_data["engine"] = {}
			ship_data["engine"]["symbol"] = re[28]
			
			re_ = self.Objman.sel(f"SELECT name, description, speed, reqi_power, reqi_crew FROM _engine WHERE engine=?", (ship_data["engine"]["symbol"],), _format=False)
			if len(re_) > 0:
				ship_data["engine"]["name"] = re_[0][0]
				ship_data["engine"]["description"] = re_[0][1] 
				speed = re_[0][2]
				reqi_power = re_[0][3]
				reqi_crew = re_[0][4]
			else:        
				ship_data["engine"]["name"] = None
				ship_data["engine"]["description"] = None
				speed = None
				reqi_power = None
				reqi_crew = None
			ship_data["engine"]["condition"] = re[29]
			ship_data["engine"]["integrity"] = re[30]
			ship_data["engine"]["speed"] = speed

			ship_data["engine"]["requirements"] = {}
			ship_data["engine"]["requirements"]["power"] = reqi_power
			ship_data["engine"]["requirements"]["crew"] = reqi_crew
				
			re_ = self.select_ship_modules(ship_data["symbol"], role=role)
			ship_data["modules"] = re_

			re_ = self.select_ship_mounts(ship_data["symbol"], role=role)
			ship_data["mounts"] = re_

			ship_data["registration"] = {}
			ship_data["registration"]["name"] = re[31]
			ship_data["registration"]["factionSymbol"] = re[36]
			ship_data["registration"]["role"] = role

			ship_data["cargo"] = {}
			ship_data["cargo"]["capacity"] = re[33]
			ship_data["cargo"]["units"] = re[34]
			ship_data["cargo"]["inventory"] = self.select_cargo(role=role)
			fleet_id = re[35]

			return ship_data

		else:
			# no ship with that name/symbol in DB

			return dict()


	def select_ship_modules(self, ship_sym:str, role:str='') -> list:
		# if role is SATELLITE return empty list
		if role == "SATELLITE":
			return list()

		com = f"SELECT modules_id FROM _ship_modules WHERE ship_sym_id=?;"
		com_var = (self.get_ship_id(ship_sym),)
		re = self.Objman.sel(com, com_var, _format=False)

		if len(re) > 0:
			re = [i[0] for i in re]
			re_list = list()

			for id_ in re:
				com = f"SELECT symbol, name, description, capacity, reqi_crew, reqi_power, reqi_slots FROM modules WHERE id=?;"
				com_var = (id_,)
				re = self.Objman.sel(com, com_var, _format=False)

				if len(re) > 0:
					re = re[0]
					pre_dict = {k: v for k, v in zip(('symbol', 'name', 'description', 'capacity', 'reqi_crew', 'reqi_power', 'reqi_slots'), re[:4])}
					reqi = {k: v for k, v in zip(('crew', 'power', 'slots'), re[4:])}
					pre_dict.update((('requirements', reqi),))

					re_list.append(pre_dict) 

				else:
					self.__class__._log.error(f"select_ship_modules has not indicated module with id {id_} in 'modules'")

					re_list.append({"id": id_})

			return re_list

		else:
			self.__class__._log.error("select_ship_modules has no modules in '_ship_modules'")

			return list()


	def select_ship_mounts(self, ship_sym:str, role:str='') -> list:
		# if role is SATELLITE return empty list
		if role == "SATELLITE":
			return list()

		com = f"SELECT mounts_id FROM _ship_mounts WHERE ship_sym_id=?;"
		com_var = (self.get_ship_id(ship_sym),)
		re = self.Objman.sel(com, com_var, _format=False)

		if len(re) > 0:
			re = [i[0] for i in re]
			re_list = list()

			for id_ in re:
				com = f"SELECT symbol, name, description, strength, deposits, reqi_crew, reqi_power FROM mounts WHERE id=?;"
				com_var = (id_,)
				re = self.Objman.sel(com, com_var, _format=False)

				if len(re) > 0:
					re = re[0]
					mount_di = {k: v for k, v in zip(('symbol', 'name', 'description', 'strength', 'deposits', 'reqi_crew', 'reqi_power'), re)}
					if mount_di["deposits"] != 0:
						mount_di["deposits"] = mount_di["deposits"].split(', ')
					re_list.append(mount_di)

				else:
					self.__class__._log.error(f"select_ship_mounts has not indicated mount with id {id_} in 'mounts'")

					re_list.append({"id": id_})

			return re_list

		else:
			self.__class__._log.error(f"select_ship_mounts has no mounts in '_ship_mounts' with '{com}, {com_var}'")

			return list()


	def select_cargo(self, role:str='') -> list:
		# if role is SATELLITE return empty list
		if role == "SATELLITE":
			return list()

		com = f"SELECT goods_id, units FROM _ship_cargo WHERE ship_sym_id=?;"
		com_var = (self.ship_id,)
		re_cargo = self.Objman.sel(com, com_var, _format=False)

		if len(re_cargo) > 0:
			

			com_var = tuple(i[0] for i in re_cargo)
			com = f"SELECT id, goods, name, description FROM _goods WHERE {create.list_or_same_col(com_var, "id")}"

			re_goods = self.Objman.sel(com, com_var, _format=False)

			if len(re_goods) == 0:
				self.__class__._log.error(f"select_cargo failed selecting from '_goods' ids {com_var}")

				return list()

			# swap order to have symbol/good as first order for sorting 
			good_sym_li = list((i[1], i[0], i[2], i[3]) for i in re_goods)
			# sort for alphabetical order
			good_sym_li.sort()

			re_cargo_dict = {str(i[0]): i[1] for i in re_cargo}
			# swap back key to be the id, now that it is alphabetical
			re_goods_dict = {str(i[1]): [i[0], i[2], i[3]] for i in good_sym_li}

			cargo_inv = list({
							"symbol": i[0],
							"name": re_goods_dict[str(i[1])][1],
							"description": re_goods_dict[str(i[1])][2],
							"units": re_cargo_dict[str(i[1])]
						} for i in good_sym_li)

			# returning sorted dict according to alphabet of symbols

			return cargo_inv

		else:
			self.__class__._log.debug(f"select_cargo '{self.name}.{self.frame.lower()}' has no cargo in '_ship_cargo' for ship_id {com_var}")

			return list()


	def del_ship_modules(self, modules:list) -> bool:
		# modules are a list of module symbols for deletion
		# multiples are meant to be deleted multiple times
		
		# get ids of the modules
		com = f"SELECT id, symbol FROM modules WHERE {create.list_or_same_col(modules, "symbol")};"
		com_var = tuple(modules)
		
		re_ = self.Objman.sel(com, com_var, _format=False)
		if len(re_) == 0:
			self.__class__._log.error(f"del_ship_modules called, but failed selection of id in 'modules' of given modules: {com_var}")

			return False

		else:
			module_ids = {i[1]: i[0] for i in re_}
			del_module_ids = {'modules_id': module_ids[v] for v in module_ids}

			# first select to make sure we don't delete two (or more) modules even though
			# we only want to delete one (according to count of argument modules)
			com = f"SELECT * FROM _ship_modules WHERE ({create.list_or_same_col(list(del_module_ids.values()), "modules_id")}) AND ship_sym_id=?;"
			vals = list(del_module_ids.values())
			vals.append(self.ship_id)

			re = self.Objman.sel(com, tuple(vals))

			if len(re) == 0:
				self.__class__._log.error(f"del_ship_modules failed selection of * in '_ship_modules' for list of deletion candidates: '{com}, {tuple(vals)}'")

				return False

			# split 3 columns
			li_ids = list()
			li_modules_ids = list()
			li_modules_sym = list()

			for entry in re:
				a, _, c = entry
				li_ids.append(a)
				li_modules_ids.append(c)
				sym = [i for i in module_ids if module_ids[i] == c]
				li_modules_sym.append(sym[0])

			# quick check if duplicates through making set
			if len(li_modules_ids) != set(li_modules_ids):
					
				# only valid case is when module symbol is less times in modules
				# than it is in li_modules_sym, where all entries pop up for the ship
				# -> so we only have to delete some indx off all 3 lists and then
				# use the (row)id to delete less than all duplicates for the ship
				less = list()
				for mod in modules:
					if modules.count(mod) < li_modules_sym.count(mod):
						less.append(mod)
					elif modules.count(mod) == li_modules_sym.count(mod):
						pass
					else:
						self.__class__._log.error("del_ship_modules deep error case with more occurances of module in modules than in the DB for that ship")

						return False

				# if no less cases, we can do the easy way without id
				if not len(less) == 0:
					# here we need to use WHERE id to only delete the amount of module(s) we have in argument modules
					for l in less:
						while modules.count(l) < li_modules_sym.count(l):
							indx = li_modules_sym.index(l)
							# now pop out of each of the 4 lists one entry
							# if we only pop out of ids and there is another occurence
							# the 2 lists are out of sync
							li_ids.pop(indx)
							li_modules_sym.pop(indx)

					# now we can uniquely use li_ids to match the right rows with WHERE
					com = f"DELETE FROM _ship_modules WHERE {create.list_or_same_col(li_ids, "id")};"

					re_ = self.Objman.del_simple(com, tuple(li_ids))

					return re_
				

			com = f"DELETE FROM _ship_modules WHERE ({create.list_or_same_col(list(del_module_ids.values()), "modules_id")}) AND ship_sym_id=?;"

			re_ = self.Objman.del_simple(com, tuple(vals))

			return re_

		# we never delete entries in table modules


	def del_ship_mounts(self, mounts:list) -> bool:
		# mounts are a list of mount symbols for deletion
		# multiples are meant to be deleted multiple times
		
		# get ids of the mounts
		com = f"SELECT id FROM mounts WHERE {create.list_or_same_col(mounts, "symbol")};"
		com_var = tuple(mounts)
		
		re_ = self.Objman.sel(com, com_var, _format=False)
		if len(re_) == 0:
			self.__class__._log.error(f"del_ship_mounts called, but failed selection of id in 'mounts' of given mounts: {com_var}")

			return False

		else:
			mount_ids = {i[1]: i[0] for i in re_}
			del_mount_ids = {'mounts_id': mount_ids[v] for v in mount_ids}

			# first select to make sure we don't delete two (or more) mounts even though
			# we only want to delete one (according to count of argument mounts)
			com = f"SELECT * FROM _ship_mounts WHERE ({create.list_or_same_col(list(del_mount_ids.values()), "mounts_id")}) AND ship_sym_id=?;"
			vals = list(del_mount_ids.values())
			vals.append(self.ship_id)

			re = self.Objman.sel(com, tuple(vals))

			if len(re) == 0:
				self.__class__._log.error(f"del_ship_mounts failed selection of * in '_ship_mounts' for list of deletion candidates: '{com}, {tuple(vals)}'")

				return False

			# split 3 columns
			li_ids = list()
			li_mounts_ids = list()
			li_mounts_sym = list()

			for entry in re:
				a, _, c = entry
				li_ids.append(a)
				li_mounts_ids.append(c)
				sym = [i for i in mount_ids if mount_ids[i] == c]
				li_mounts_sym.append(sym[0])

			# quick check if duplicates through making set
			if len(li_mounts_ids) != set(li_mounts_ids):
					
				# only valid case is when mount symbol is less times in mounts
				# than it is in li_mounts_sym, where all entries pop up for the ship
				# -> so we only have to delete some indx off all 3 lists and then
				# use the (row)id to delete less than all duplicates for the ship
				less = list()
				for mnt in mounts:
					if mounts.count(mnt) < li_mounts_sym.count(mnt):
						less.append(mnt)
					elif mounts.count(mnt) == li_mounts_sym.count(mnt):
						pass
					else:
						self.__class__._log.error("del_ship_mounts deep error case with more occurances of mount in mounts than in the DB for that ship")

						return False

				# if no less cases, we can do the easy way without id
				if not len(less) == 0:
					# here we need to use WHERE id to only delete the amount of mount(s) we have in argument mounts
					for l in less:
						while mounts.count(l) < li_mounts_sym.count(l):
							indx = li_mounts_sym.index(l)
							# now pop out of each of the 4 lists one entry
							# if we only pop out of ids and there is another occurence
							# the 2 lists are out of sync
							li_ids.pop(indx)
							li_mounts_sym.pop(indx)

					# now we can uniquely use li_ids to match the right rows with WHERE
					com = f"DELETE FROM _ship_mounts WHERE {create.list_or_same_col(li_ids, "id")};"

					re_ = self.Objman.del_simple(com, tuple(li_ids))

					return re_
				

			com = f"DELETE FROM _ship_mounts WHERE ({create.list_or_same_col(list(del_mount_ids.values()), "mounts_id")}) AND ship_sym_id=?;"

			re_ = self.Objman.del_simple(com, tuple(vals))

			return re_

		# we never delete entries in table mounts


	def update_ship(self, DB_state:dict) -> bool:

		def _equal(key:str) -> bool:
			return self.jj[key] == DB_state[key]
		
		# get differences on top level
		updateable = ("nav", "crew", "fuel", "cooldown", "frame", "reactor", "engine", 
						"modules", "mounts", "cargo")
		diff = [i for i in updateable if not _equal(i)]

		if len(diff) == 0:
			return False

		direct_updt = dict()

		if "nav" in diff:
			if not self.jj["nav"]["systemSymbol"] == DB_state["nav"]["systemSymbol"]:
				direct_updt.update({"systemsymbol": self.jj["nav"]["systemSymbol"]})
			if not self.jj["nav"]["waypointSymbol"] == DB_state["nav"]["waypointSymbol"]:
				direct_updt.update({"waypoints_id": self.get_wp_id(self.waypoint)})
			if not self.jj["nav"]["route"] == DB_state["nav"]["route"]:
				if not self.jj["nav"]["route"] == DB_state["nav"]["route"]:
					direct_updt.update({
						"origin_wp_id": self.get_wp_id(self.jj["nav"]["route"]["origin"]["symbol"]),
						"destination_wp_id": self.get_wp_id(self.jj["nav"]["route"]["destination"]["symbol"]),
						"arrival": ISO_to_epoch(self.jj["nav"]["route"]["arrival"]),
						"departure": ISO_to_epoch(self.jj["nav"]["route"]["departureTime"])
						})
			if not self.jj["nav"]["status"] == DB_state["nav"]["status"]:
				direct_updt.update({"status": self.jj["nav"]["status"]})
			if not self.jj["nav"]["flightMode"] == DB_state["nav"]["flightMode"]:
					direct_updt.update({"flightMode": self.jj["nav"]["flightMode"]})

		if "crew" in diff:
			if not self.jj["crew"]["current"] == DB_state["crew"]["current"]:
				direct_updt.update({"crew_curr": self.jj["crew"]["current"]})
			if not self.jj["crew"]["capacity"] == DB_state["crew"]["capacity"]:
				direct_updt.update({"crew_capa": self.jj["crew"]["capacity"]})
			if not self.jj["crew"]["required"] == DB_state["crew"]["required"]:
				direct_updt.update({"crew_requ": self.jj["crew"]["required"]})
			if not self.jj["crew"]["rotation"] == DB_state["crew"]["rotation"]:
				direct_updt.update({"crew_rotation": self.jj["crew"]["rotation"]})
			if not self.jj["crew"]["morale"] == DB_state["crew"]["morale"]:
				direct_updt.update({"crew_morale": self.jj["crew"]["morale"]})
			if not self.jj["crew"]["wages"] == DB_state["crew"]["wages"]:
				direct_updt.update({"crew_wages": self.jj["crew"]["wages"]})

		if "fuel" in diff:
			if not self.jj["fuel"]["current"] == DB_state["fuel"]["current"]:
				direct_updt.update({"fuel_curr": self.jj["fuel"]["current"]})
			if not self.jj["fuel"]["capacity"] == DB_state["fuel"]["capacity"]:
				direct_updt.update({"fuel_capa": self.jj["fuel"]["capacity"]})
			if not self.jj["fuel"]["consumed"] == DB_state["fuel"]["consumed"]:
				direct_updt.update({
					"fuel_cons_amt": self.jj["fuel"]["consumed"]["amount"],
					"fuel_cons_time": ISO_to_epoch(self.jj["fuel"]["consumed"]["timestamp"])
					})

		if "cooldown" in diff:
			direct_updt.update({
				"cd_secs": self.jj["cooldown"]["totalSeconds"],
				"cd_expiration": ISO_to_epoch(self.jj["cooldown"]["expiration"]) if "expiration" in self.jj["cooldown"] else 0
				})

		if "frame" in diff:
			direct_updt.update({
				"frame_condition": round(self.jj["frame"]["condition"], 4),
				"frame_integrity": round(self.jj["frame"]["integrity"], 4)
				})

		if "reactor" in diff:
			direct_updt.update({
				"reactor_condition": round(self.jj["reactor"]["condition"], 4),
				"reactor_integrity": round(self.jj["reactor"]["integrity"], 4)
				})

		if "engine" in diff:
			direct_updt.update({
				"engine_condition": round(self.jj["engine"]["condition"], 4),
				"engine_integrity": round(self.jj["engine"]["integrity"], 4)
				})

		if "modules" in diff:
			# need to keep duplicates and compare with them
			li_jjmod = Counter(list(i["symbol"] for i in self.jj["modules"]))
			li_DBmod = Counter(list(i["symbol"] for i in DB_state["modules"]))

			new_ins = li_jjmod - li_DBmod
			old_del = li_DBmod - li_jjmod
			new_ins = list(new_ins.elements())
			old_del = list(old_del.elements())
			new_ins.sort()
			old_del.sort()

			new_ins_dictlist = list()
			for item in new_ins:
				new_ins_dictlist.append(next(i for i in self.jj["modules"] if i["symbol"] == item))

			# delete is being done through a list of symbols
			if len(old_del) > 0 and not self.del_ship_modules(old_del):
				self.__class__._log.error(f"update_ship {self.name}.{self.frame.lower()} failed deleting old modules {old_del}")
			# insert is being done through a list of dictionaries, containing all info
			if len(new_ins) > 0 and not self.insert_ship_modules(new_ins_dictlist, self.ship_id):
				self.__class__._log.error(f"update_ship {self.name}.{self.frame.lower()} failed updating new modules {new_ins}")

		if "mounts" in diff:
			# need to keep duplicates and compare with them
			li_jjmnt = Counter(list(i["symbol"] for i in self.jj["mounts"]))
			li_DBmnt = Counter(list(i["symbol"] for i in DB_state["mounts"]))

			new_ins = li_jjmnt - li_DBmnt
			old_del = li_DBmnt - li_jjmnt
			new_ins = list(new_ins.elements())
			old_del = list(old_del.elements())
			new_ins.sort()
			old_del.sort()

			new_ins_dictlist = list()
			for item in new_ins:
				new_ins_dictlist.append(next(i for i in self.jj["mounts"] if i["symbol"] == item))
			
			# delete is being done through a list of symbols
			if len(old_del) > 0 and not self.del_ship_mounts(old_del):
				self.__class__._log.error(f"update_ship {self.name}.{self.frame.lower()} failed deleting old mounts {old_del}")
			# insert is being done through a list of dictionaries, containing all info
			if len(new_ins) > 0 and not self.insert_ship_mounts(new_ins, self.ship_id):
				self.__class__._log.error(f"update_ship {self.name}.{self.frame.lower()} failed updating new mounts {new_ins}")

		if "cargo" in diff:
			if not self.jj["cargo"]["capacity"] == DB_state["cargo"]["capacity"]:
				direct_updt.update({"cargo_capa": self.jj["cargo"]["capacity"]})
			if not self.jj["cargo"]["units"] == DB_state["cargo"]["capacity"]:
				direct_updt.update({"cargo_units": self.jj["cargo"]["units"]})
				
			if not self.jj["cargo"]["inventory"] == DB_state["cargo"]["inventory"]:
				if not self.update_cargo(self.jj["cargo"]["inventory"], self.ship_id):
					self.__class__._log.error("update_ship {}.{} failed updating cargo {}".format(self.name, self.frame.lower(), self.jj["cargo"]["inventory"]))		
			
		direct_updt.update({"updated": int(time.time())})

		# exec direct_updt
		if not self.Objman.updt(table="ships", cols=list(direct_updt.keys()), vals=list(direct_updt.values()), unique={"id": self.ship_id}):
			self.__class__._log.error("update_ship failed updating {}.{} with direct_updt data on changes in {}".format(self.name, self.frame.lower(), diff))

		return True


	def update_cargo(self, cargo_inv:list, ship_sym_id: Union[int, None]=None) -> bool:
		# cargo_inv is a list of dicts with specific goods
		
		# get ids of the goods
		cargo_symbols = [i["symbol"] for i in cargo_inv]
		# selecting name and description, to also be able to update in case they are None/NULL
		com = f"SELECT id, goods, name, description FROM _goods WHERE {create.list_or_same_col(cargo_symbols, "goods")};"
		com_var = tuple(cargo_symbols)
		
		re_ = self.Objman.sel(com, com_var, _format=False)
		if len(re_) == 0:
			self.__class__._log.error(f"update_cargo failed selection of id in '_goods' of given cargo symbols: {com_var}")

			return False

		# update_goods for goods that don't have complete data
		to_update = [i[1] for i in re_ if None in (i[2], i[3])]
		goods_update = {}
		for good in re_:
			if good[1] in to_update:
				# compose keys as column names and values as cells
				goods_update.update({"name": good[2], "description": good[3], "updated": int(time.time())})
		
		if not self.Objman.updt(table="_goods", cols=list(goods_update.keys()), vals=list(goods_update.values()), unique={"goods": i for i in to_update}):
			self.__class__._log.error(f"update_cargo failed updating name, description of goods {to_update}")

		goods_ids = [i[0] for i in re_]
		# check if all goods from cargo_inv are in table _goods
		if len(goods_ids) != len(cargo_inv):
			# need to insert some goods into table _goods first
			re_goods_sym = set(i[1] for i in re_)
			to_insert = sorted(list(set(cargo_symbols)-re_goods_sym))

			if not self.insert_cargo([i for i in cargo_inv if i["symbol"] in to_insert], self.ship_id):
				self.__class__._log.error(f"update_cargo failed insert cargo because of unknown goods: {to_insert}")

				return False

			re_ = self.Objman.sel(com, com_var, _format=False)

		# make dict with inv_goods_symbol and values inv_goods_id
		di_inv_goods = {i[1]: i[0] for i in re_}

		for good in cargo_inv:

			re = self.Objman.sel("SELECT units FROM _ship_cargo WHERE ship_sym_id=? AND goods_id=?", (self.ship_id, di_inv_goods[good["symbol"]]), _format=False)

			# re has 0 len if good is not in there
			if len(re) == 0:
				# good should be in there, since self.insert_cargo ran already
				self.__class__._log.error("update_cargo failed select of good '{}' from ship '{}:{}' although insert_cargo should have inserted it".format(good["symbol"], self.name, self.ship_id))

				return False

			# check for right units amount
			if re[0][0] != good["units"]:
				cols = ["units"]
				vals = [good["units"]]

				uniq = {"ship_sym_id": self.ship_id, "goods_id": di_inv_goods[good["symbol"]]}

				# update units amount
				if not self.Objman.updt(table="_ship_cargo", cols=cols, vals=vals, unique=uniq):
					self.__class__._log.error("update_cargo failed updating units of {} for {}.{}".format(good["symbol"], self.name, self.ship_id))
					
					return False

		return True


	def updt_sdf(self) -> bool:
		_di = copy.deepcopy(self.jj)
		
		# update dict for sdf
		_di.update({
						"modules": [i["symbol"] for i in _di["modules"]],
						"mounts": [i["symbol"] for i in _di["mounts"]],
						"has_task": self.has_task,
						"task_id": self.task_id,
						"ship_id": self.ship_id,
						"fleet": self.fleet,
						"GmCrd": self.coordinates
					})

		# also update all str timestamps to epoch
		_di["nav"]["route"]["arrival"] = ISO_to_epoch(_di["nav"]["route"]["arrival"])
		_di["nav"]["route"]["departureTime"] = ISO_to_epoch(_di["nav"]["route"]["departureTime"])
		_di["fuel"]["consumed"]["timestamp"] = ISO_to_epoch(_di["fuel"]["consumed"]["timestamp"])
		if "expiration" in _di and isinstance(_di["cooldown"]["expiration"], str):
			_di["cooldown"]["expiration"] = ISO_to_epoch(_di["cooldown"]["expiration"])
		elif "expiration" not in _di:
			_di["cooldown"]["expiration"] = 0

		df = pd.json_normalize(_di)

		if self.sdf is not None and "symbol" in self.sdf[0].columns and any(self.sdf[0].symbol.str.fullmatch(self.name)):
			# Create a copy of the existing DataFrame to get the dtypes
			if len(self.sdf[0]) > 0:
				# Get dtypes from existing DataFrame
				dtypes = self.sdf[0].dtypes.to_dict()
				
				# Convert columns in the new DataFrame to match the dtypes of the existing DataFrame
				# convert columns prone to int/float changes
				for col in ("frame.condition", "frame.integrity",
							"engine.condition", "engine.integrity",
							"reactor.condition", "reactor.integrity"):
					if col in dtypes:
						try:
							df[col] = df[col].astype(dtypes[col])
						except (ValueError, TypeError):
							# If conversion fails, keep the original dtype
							pass
			
			# Now update the DataFrame with type-compatible values
			self.sdf[0].loc[self.sdf[0]["symbol"] == self.name] = df.loc[df['symbol'] == self.name]
		elif self.sdf is not None and "symbol" in self.sdf[0].columns:
			self.sdf[0] = pd.concat([self.sdf[0], df])
		else:
			self.sdf[0] = df

		return True


	def has_mount(self, module:str) -> bool:

		return any(module in i["symbol"] for i in self.jj["mounts"])
