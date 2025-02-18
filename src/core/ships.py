# ships
import time
from functools import partial
from typing import Union

from core.utils import coord, meta, netw
from core.waypoints import Waypoint
from utils.list import create
from utils.sql import strings
from utils.time import ISO_to_epoch, conv_time_time_to_def
from hkeep.log.logger import get_logger


class Ship:

	_log = get_logger(__name__)
	inventory = dict()

	@classmethod
	def api_get_pages(cls, Sess, url:str, re_dec:dict) -> list:
		data = list()

		# prepare while
		limit = False
		page = 0
		url_p = url+"?page={page}"
		url = url_p.format(page=2)
		
		# pull more pages if meta indicates further pages or upping limit
		while meta.needs_more_pages(re_dec["meta"]):
			# go another cycle
			if not limit and "limit" not in url_p:
				page = 2
				re = Sess.get(url=url)
				
				url_p = url_p+"&limit={limit}"

			else:
				if not limit:
					limit = True
					url = url_p.format(page=2, limit=20)

				else:
					page += 1
					url = url_p.format(page=page, limit=20)

				re = Sess.get(url=url)

			
			if netw.validate_re(re, cls._log.error, f"api_get_ships needs_more_pages failed to get ships for Fleet '{self.fleet}'"):
				re_dec = re.Response.json()
				data.extend(re_dec["data"])
			else:
				break

		return data


	@classmethod
	def get_ship_id(cls, SqlHan, ship_sym:str) -> Union[int, None]:
		re = SqlHan.sel(f"SELECT id FROM ships WHERE symbol=?;", (ship_sym,), _format=False)

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


	def __init__(self, jj:dict, Sess, Conf, SqlHan, fleet:str):
		self.jj = jj
		self.Sess = Sess
		self.Conf = Conf
		self.SqlHan = SqlHan
		self.fleet = fleet

		self.get_wp_id = partial(Waypoint.get_wp_id, Sess, Conf, SqlHan)
		self.get_wp_sym = partial(Waypoint.get_wp_sym, SqlHan)
		self.insert_wp = partial(Waypoint.insert_wp, SqlHan)
		self.get_ship_id = partial(self.__class__.get_ship_id, SqlHan)

		if self.jj["frame"] is None:
			self.jj = self.select_ship()

		self.__class__._log.info(f"new ship '{self.name}.{self.frame.lower()}' added to fleet '{fleet}'")


	@property
	def name(self) -> str:
		return self.jj["symbol"]

	@property
	def ship_id(self) -> str:
		return self.__class__.get_ship_id(self.SqlHan, self.name)

	@property
	def frame(self) -> int:
		return self.jj["frame"]["name"]

	@property
	def role(self) -> int:
		return self.jj["registration"]["role"]

	@property
	def status(self) -> int:
		return self.jj["nav"]["status"]

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
		_t = self.jj["nav"]["route"]["destination"]

		coord = coord.GameCoord(int(_t["x"]), int(_t["y"]), _t["symbol"])

		return coord

	@property
	def waypoint(self) -> int:
		return self.jj["nav"]["waypointSymbol"]

	@property
	def engineSpeed(self) -> int:
		return self.jj["engine"]["speed"]

	@property
	def cargoInv(self) -> int:
		return self.jj["cargo"]["inventory"]


	def _update_state(self, inp:dict):
		self.jj.update(inp["data"])

		DB_state = self.select_ship()
		# if DB state not memory state
		if not DB_state == self.jj:
			self.update_ship(DB_state)


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

		multiplier = self.Conf.config["NAVIGATION_MULTIPLIER"][mode]
		
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


	def go_waypoint(self, coord:coord.GameCoord, mode:str="CRUISE") -> bool:
		
		if not self.in_range(coord, mode=mode):
			_log.error(f"go_waypoint {self.name}.{self.frame.lower()} to {coord} failed because ship is out of range")

			return False

		# we have enough fuel to go to coord

		# check if we are in orbit, if not, go there
		if self.status != "IN_ORBIT" and not self.go_orbit():
			_log.error(f"go_waypoint {self.name}.{self.frame.lower()} to {coord} failed because ship failed going to orbit first")

			return False

		# we are in orbit and can go now
		url, data = self.Conf.config["sites"]["SPACETRADERS"]["POST"]["GO_WAYPOINT"]

		url = url.format(ShipSymbol=self.name)
		data.update({"WaypointSymbol": coord.wp})

		re = self.Sess.post(url=url, data=data)

		if re.Response.status_code in (200, 201):
			_log.info(f"{self.name}.{self.frame.lower()} on the way to {coord}")
			
			# need to update Ship state in self.jj
			self._update_state(json.loads(re.Response.content.decode()))

			# need to patch flightMode
			if self.flightMode != mode:
				# TODO send patch request
				pass
			
			return True

		else:
			_log.error(f"go_waypoint {self.name}.{self.frame.lower()} to {coord} failed ({re.Response._reqID})")

			return False


	def go_orbit(self) -> bool:
		url = self.Conf.config["sites"]["SPACETRADERS"]["POST"]["GO_ORBIT"]

		url = url.format(ShipSymbol=self.name)

		re = self.Sess.post(url=url, data=dict())

		if re.Response.status_code in (200, 201):
			_log.info(f"{self.name}.{self.frame.lower()} went to orbit {coord}")
			
			# need to update Ship state in self.jj
			self._update_state(json.loads(re.Response.content.decode()))
			
			return True

		else:
			_log.error(f"go_orbit {self.name}.{self.frame.lower()} failed to orbit at {coord} ({re.Response._reqID})")

			return False


	def go_dock(self) -> bool:
		url = self.Conf.config["sites"]["SPACETRADERS"]["POST"]["DOCK_SHIP"]

		url = url.format(ShipSymbol=self.name)

		re = self.Sess.post(url=url, data=dict())

		if re.Response.status_code in (200, 201):
			_log.info(f"{self.name}.{self.frame.lower()} went to dock {coord}")
			
			# need to update Ship state in self.jj
			self._update_state(json.loads(re.Response.content.decode()))
			
			return True

		else:
			_log.error(f"go_dock {self.name}.{self.frame.lower()} failed to dock at {coord} ({re.Response._reqID})")

			return False


	def extract_ores(self) -> bool:
		# check if we are in orbit, if not, go there
		if self.status != "IN_ORBIT" and not self.go_orbit():
			_log.error(f"extract_ores {self.name}.{self.frame.lower()} from {coord} failed because ship failed going to orbit first")

			return False

		# we are in orbit, we can extract now
		url = self.Conf.config["sites"]["SPACETRADERS"]["POST"]["EXTRACT_ORES"]

		url = url.format(miningShipSymbol=self.name)

		re = self.Sess.post(url=url, data=dict())

		if re.Response.status_code in (200, 201):
			_log.info(f"{self.name}.{self.frame.lower()} started extracting ores at {coord}")
			
			# need to update Ship state in self.jj
			self._update_state(json.loads(re.Response.content.decode()))
			
			return True

		else:
			_log.error(f"extract_ores {self.name}.{self.frame.lower()} failed to start extracting ores at {coord} ({re.Response._reqID})")

			return False


	def refuel(self) -> bool:
		# one unit at MARKETPLACE replenishes 100 units in ship tank
		url = self.Conf.config["sites"]["SPACETRADERS"]["POST"]["REFUEL"]

		url = url.format(ShipSymbol=self.name)

		re = self.Sess.post(url=url, data=dict())

		if re.Response.status_code in (200, 201):
			_log.info(f"{self.name}.{self.frame.lower()} refueled at {coord}")
			
			# need to update Ship state in self.jj
			self._update_state(json.loads(re.Response.content.decode()))
			
			return True

		else:
			_log.error(f"refuel {self.name}.{self.frame.lower()} at {coord} ({re.Response._reqID})")

			return False


	def sell_good(self, good:str, quantity:int) -> bool:
		url, data = self.Conf.config["sites"]["SPACETRADERS"]["POST"]["SELL"]

		url = url.format(ShipSymbol=self.name)
		data.update({"symbol": good, "units": str(quantity)})
		
		re = self.Sess.post(url=url, data=data)

		if re.Response.status_code in (200, 201):
			_log.info(f"{self.name}.{self.frame.lower()} sold {quantity} {good} at {self.waypoint} market")

			return True

		else:
			_log.error(f"{self.name}.{self.frame.lower()} failed selling {quantity} {good} at {self.coordinates} market ({re.Response._reqID})")

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
							"cd_expiration": ISO_to_epoch(ship_data["cooldown"]["expiration"]) if "expiration" in ship_data["cooldown"] else 0,
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

			if self.SqlHan.ins("ships", list(sptr_ship.values()), extras=extras):
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

			re = self.SqlHan.sel(com, com_var, _format=False)

			if len(re) == 0:
				# append time for updated column
				vals = list(module.values())
				vals.append(int(time.time()))

				# handle case when module doesn't have field
				# capacity
				if "capacity" not in module:
						vals.insert(3, 0)

				if self.SqlHan.ins("modules", vals):
					self.__class__._log.info("new ship module '{}' added".format(module["symbol"]))

					re = self.SqlHan.sel(com, com_var, _format=False)
					module_id = re[0][0]

					if not self.SqlHan.ins("_ship_modules", [ship_sym_id, module_id]):
						self.__class__._log.error(f"handle_ship_modules failed insert in '_ship_modules': {[ship_sym_id, module_id]}")
						
						return False

				else:
					self.__class__._log.error(f"handle_ship_modules failed insert in 'modules': {vals}")
					
					return False

			else:
				module_id = re[0][0]

				com = f"SELECT * FROM _ship_modules WHERE ship_sym_id=? AND modules_id=?;"
				com_var = (ship_sym_id, module_id)

				re = self.SqlHan.sel(com, com_var, _format=False)

				if len(re) == 0:
					if not self.SqlHan.ins("_ship_modules", [ship_sym_id, module_id]):
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

			re = self.SqlHan.sel(com, com_var, _format=False)

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

				if self.SqlHan.ins("mounts", vals):
					self.__class__._log.info("new ship mount '{}' added".format(mount["symbol"]))

					re = self.SqlHan.sel(com, com_var, _format=False)
					mount_id = re[0][0]

					if not self.SqlHan.ins("_ship_mounts", [ship_sym_id, mount_id]):
						self.__class__._log.error(f"handle_ship_mounts failed insert in '_ship_mounts': {[ship_sym_id, mount_id]}")

						return False

				else:
					self.__class__._log.error(f"handle_ship_mounts failed insert in 'mounts': {vals}")
					
					return False

			else:
				mount_id = re[0][0]

				com = f"SELECT * FROM _ship_mounts WHERE ship_sym_id=? AND mounts_id=?;"
				com_var = (ship_sym_id, mount_id)

				re = self.SqlHan.sel(com, com_var, _format=False)

				if len(re) == 0:
					if not self.SqlHan.ins("_ship_mounts", [ship_sym_id, mount_id]):
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

			re = self.SqlHan.sel(com, com_var, _format=False)

			# unknown good needs to be inserted into _goods
			if len(re) == 0:
				# last value is units, which we don't need in goods
				vals = list(good.values())[:-1]
				# adding time for updated column
				vals.append(int(time.time()))

				if not self.SqlHan.ins("_goods", vals):
					self.__class__._log.error(f"insert_cargo failed insert of new good '{good["symbol"]}'")

					return False

				else:
					self.__class__._log.info("new good '{}' added".format(good["symbol"]))

				re = self.SqlHan.sel(com, com_var, _format=False)

			# known good needs to be inserted into _ship_cargo
			good_id = re[0][0]

			if not self.SqlHan.ins("_ship_cargo", [good_id, ship_sym_id, good["units"], int(time.time())]):
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
		re = self.SqlHan.sel(com, com_var, _format=False)

		if len(re) > 0:
			re = re[0]

			ship_data = {}
			ship_data["symbol"] = re[0]
			
			ship_data["nav"] = {}
			ship_data["nav"]["systemSymbol"] = re[1]
			ship_data["nav"]["waypointSymbol"] = self.get_wp_sym(re[2])

			ship_data["nav"]["route"] = {}
			ship_data["nav"]["route"]["origin"] = {}
			ship_data["nav"]["route"]["origin"]["symbol"] = self.get_wp_sym(re[3])
			
			re_ = self.SqlHan.sel(f"SELECT wp_type, systemsymbol, coords FROM waypoints WHERE wp_symbol=?", (ship_data["nav"]["route"]["origin"]["symbol"],), _format=False)
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
			
			re_ = self.SqlHan.sel(f"SELECT wp_type, systemsymbol, coords FROM waypoints WHERE wp_symbol=?", (ship_data["nav"]["route"]["destination"]["symbol"],), _format=False)
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
			
			re_ = self.SqlHan.sel(f"SELECT name, description, moduleSlots, mountPoints, fuelCapa, reqi_power, reqi_crew FROM _frame WHERE frame=?", (ship_data["frame"]["symbol"],), _format=False)
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

			re_ = self.SqlHan.sel(f"SELECT name, description, power_output, reqi_crew FROM _reactor WHERE reactor=?", (ship_data["reactor"]["symbol"],), _format=False)
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
			
			re_ = self.SqlHan.sel(f"SELECT name, description, speed, reqi_power, reqi_crew FROM _engine WHERE engine=?", (ship_data["engine"]["symbol"],), _format=False)
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
				
			re_ = self.select_ship_modules(ship_data["symbol"])
			ship_data["modules"] = re_

			re_ = self.select_ship_mounts(ship_data["symbol"])
			ship_data["mounts"] = re_

			ship_data["registration"] = {}
			ship_data["registration"]["name"] = re[31]
			ship_data["registration"]["factionSymbol"] = re[36]
			ship_data["registration"]["role"] = re[32]

			ship_data["cargo"] = {}
			ship_data["cargo"]["capacity"] = re[33]
			ship_data["cargo"]["units"] = re[34]
			ship_data["cargo"]["inventory"] = self.select_cargo()
			fleet_id = re[35]

			return ship_data

		else:
			# no ship with that name/symbol in DB

			return dict()


	def select_ship_modules(self, ship_sym:str) -> list:
		com = f"SELECT modules_id FROM _ship_modules WHERE ship_sym_id=?;"
		com_var = (self.get_ship_id(ship_sym),)
		re = self.SqlHan.sel(com, com_var, _format=False)

		if len(re) > 0:
			re = [i[0] for i in re]
			re_list = list()

			for id_ in re:
				com = f"SELECT symbol, name, description, capacity, reqi_crew, reqi_power, reqi_slots FROM modules WHERE id=?;"
				com_var = (id_,)
				re = self.SqlHan.sel(com, com_var, _format=False)

				if len(re) > 0:
					re = re[0]
					re_list.append({k: v for k, v in zip(('symbol', 'name', 'description', 'capacity', 'reqi_crew', 'reqi_power', 'reqi_slots'), re)}) 

				else:
					self.__class__._log.error(f"select_ship_modules has not indicated module with id {id_} in 'modules'")

					re_list.append({"id": id_})

			return re_list

		else:
			self.__class__._log.error("select_ship_modules has no modules in '_ship_modules'")

			return list()


	def select_ship_mounts(self, ship_sym:str) -> list:
		com = f"SELECT mounts_id FROM _ship_mounts WHERE ship_sym_id=?;"
		com_var = (self.get_ship_id(ship_sym),)
		re = self.SqlHan.sel(com, com_var, _format=False)

		if len(re) > 0:
			re = [i[0] for i in re]
			re_list = list()

			for id_ in re:
				com = f"SELECT symbol, name, description, strength, deposits, reqi_crew, reqi_power FROM mounts WHERE id=?;"
				com_var = (id_,)
				re = self.SqlHan.sel(com, com_var, _format=False)

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


	def select_cargo(self) -> list:
		com = f"SELECT goods_id, units FROM _ship_cargo WHERE ship_sym_id=?;"
		com_var = (self.ship_id,)
		re = self.SqlHan.sel(com, com_var, _format=False)

		if len(re) > 0:
			goods_inv = list()

			com_var = tuple(i[0] for i in re)
			com = f"SELECT id, goods, name, description FROM _goods WHERE {create.list_or_same_col(com_var, "id")}"

			re_goods = self.SqlHan.sel(com, com_var, _format=False)

			if len(re_goods) == 0:
				self.__class__._log.error(f"select_cargo failed selecting from '_goods' ids {com_var}")

				return list()

			good_sym_li = list((i[1], i[0]) for i in re_goods)
			# sort for alphabetical order
			good_sym_li.sort()

			re_dict = {i[0]: i[1] for i in re}
			re_goods_dict = {i[0]: [i[1], i[2], i[3]] for i in re}

			cargo_inv = list({
							"symbol": i[0],
							"name": re_goods_dict[i[1]][1],
							"description": re_goods_dict[i[1]][2],
							"units": re_dict[i[1]]
						} for i in good_sym_li)

			# returning sorted dict according to alphabet of symbols

			return cargo_inv

		else:
			self.__class__._log.error(f"select_cargo failed selecting from '_ship_cargo' ids for ship_id {com_var}")

			return list()


	def del_ship_modules(self, modules:list) -> bool:
		# modules are a list of dicts with specific modules
		
		# get ids of the modules
		com = f"SELECT id FROM modules WHERE {create.list_or_same_col(modules, "symbol")};"
		com_var = tuple(modules)
		
		re_ = self.SqlHan.sel(com, com_var, _format=False)
		if len(re_) == 0:
			self.__class__._log.error(f"del_ship_modules called, but failed selection of id in 'modules' of given modules: {com_var}")

			return False

		else:
			mount_ids = [i[0] for i in re_]
			del_mount_ids = {'modules_id': v for v in mount_ids}

			com = f"DROP FROM _ship_modules WHERE ({create.list_or_same_col(list(del_mount_ids.values()), "modules_id")}) AND ship_sym_id=?;"
 
			vals = list(del_mount_ids.values())
			vals.append(self.ship_id)

			re_ = self.SqlHan.del_simple(com, tuple(vals))

			return re_

		# we never delete entries in table modules


	def del_ship_mounts(self, mounts:list) -> bool:
		# mounts are a list of dicts with specific mounts
		
		# get ids of the mounts
		com = f"SELECT id FROM mounts WHERE {create.list_or_same_col(mounts, "symbol")};"
		com_var = tuple(mounts)
		
		re_ = self.SqlHan.sel(com, com_var, _format=False)
		if len(re_) == 0:
			self.__class__._log.error(f"del_ship_mounts called, but failed selection of id in 'mounts' of given mounts: {com_var}")

			return False

		else:
			mount_ids = [i[0] for i in re_]
			del_mount_ids = {'mounts_id': v for v in mount_ids}

			com = f"DROP FROM _ship_mounts WHERE ({create.list_or_same_col(list(del_mount_ids.values()), "mounts_id")}) AND ship_sym_id=?;"
 
			vals = list(del_mount_ids.values())
			vals.append(self.ship_id)

			re_ = self.SqlHan.del_simple(com, tuple(vals))

			return re_

		# we never delete entries in table mounts


	def update_ship(self, DB_state:dict) -> bool:

		def _equal(key:str) -> bool:
			return self.jj[key] == DB_state[key]
		
		# get differences on top level
		updateable = ("nav", "crew", "fuel", "cooldown", "frame", "reactor", "enigne", 
						"modules", "mounts", "cargo")
		diff = [i for i in updateable if not _equal(i)]

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
				"frame_condition": self.jj["frame"]["condition"],
				"frame_integrity": ISO_to_epoch(self.jj["frame"]["integrity"])
				})

		if "reactor" in diff:
			direct_updt.update({
				"reactor_condition": self.jj["reactor"]["condition"],
				"reactor_integrity": ISO_to_epoch(self.jj["reactor"]["integrity"])
				})

		if "enigne" in diff:
			direct_updt.update({
				"enigne_condition": self.jj["enigne"]["condition"],
				"enigne_integrity": ISO_to_epoch(self.jj["enigne"]["integrity"])
				})

		if "modules" in diff:
			set_jjmod = set(i["symbol"] for i in self.jj["modules"])
			set_DBmod = set(i["symbol"] for i in DB_state["modules"])
			# also getting rid of duplicates

			new_ins = sorted(list(set_jjmod-set_DBmod))
			old_del = sorted(list(set_DBmod-set_jjmod))

			if len(old_del) > 0 and not self.del_ship_modules(old_del):
				self.__class__._log.error(f"update_ship {self.name}.{self.frame.lower()} failed deleting old modules {old_del}")
			if len(new_ins) > 0 and not self.insert_ship_modules(new_ins, self.ship_id):
				self.__class__._log.error(f"update_ship {self.name}.{self.frame.lower()} failed updating new modules {new_ins}")

		if "mounts" in diff:
			set_jjmnt = set(i["symbol"] for i in self.jj["mounts"])
			set_DBmnt = set(i["symbol"] for i in DB_state["mounts"])
			# also getting rid of duplicates

			new_ins = sorted(list(set_jjmnt-set_DBmnt))
			old_del = sorted(list(set_DBmnt-set_jjmnt))
			
			if len(old_del) > 0 and not self.del_ship_mounts(old_del):
				self.__class__._log.error(f"update_ship {self.name}.{self.frame.lower()} failed deleting old mounts {old_del}")
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
			
		if len(diff) > 0:
			direct_updt.update({"updated": int(time.time())})

		# exec direct_updt
		if not self.SqlHan.updt(table="ships", cols=list(direct_updt.keys()), vals=list(direct_updt.values()), unique={"id": self.ship_id}):
			self.__class__._log.error("update_ship failed updating {}.{} with direct_updt data on changes in {}".format(self.name, self.frame.lower(), diff))

		return True


	def update_cargo(self, cargo_inv:list, ship_sym_id: Union[int, None]=None) -> bool:
		# cargo_inv is a list of dicts with specific goods
		
		# get ids of the goods
		cargo_symbols = [i["symbol"] for i in cargo_inv]
		com = f"SELECT id, goods FROM _goods WHERE {create.list_or_same_col(cargo_symbols, "goods")};"
		com_var = tuple(cargo_symbols)
		
		re_ = self.SqlHan.sel(com, com_var, _format=False)
		if len(re_) == 0:
			self.__class__._log.error(f"update_cargo failed selection of id in '_goods' of given cargo symbols: {com_var}")

			return False

		goods_ids = [i[0] for i in re_]
		# check if all goods from cargo_inv are in table _goods
		if not len(goods_ids) == len(cargo_inv):
			# need to insert some goods into table _goods first
			re_goods_sym = set(i[1] for i in re_)
			to_insert = sorted(list(set(cargo_symbols)-re_goods_sym))

			if not self.insert_cargo([i for i in cargo_inv if i["symbol"] in to_insert], self.ship_id):
				self.__class__._log.error(f"update_cargo failed insert cargo because of unknown goods: {to_insert}")

				return False

			re_ = self.SqlHan.sel(com, com_var, _format=False)

		# make dict with inv_goods_symbol and values inv_goods_id
		di_inv_goods = {i[1]: i[0] for i in re_}

		for good in cargo_inv:

			re = self.SqlHan.sel("SELECT units FROM _ship_cargo WHERE ship_sym_id=? AND goods_id=?", (self.ship_id, di_inv_goods[good["symbol"]]), _format=False)

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
				if not self.SqlHan.updt(table="_ship_cargo", cols=cols, vals=vals, unique=uniq):
					self.__class__._log.error("update_cargo failed updating units of {} for {}.{}".format(good["symbol"], self.name, self.ship_id))
					
					return False

		return True
