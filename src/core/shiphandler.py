# shiphandler
import json, time
import pandas as pd
from functools import partial
from typing import Union

from core.ships import Ship
from core.utils import coord, meta
from core.utils.objmanager import ObjManager
from hkeep.log.logger import get_logger
from utils.time import ISO_to_epoch


class ShipHandler:

	_log = get_logger(__name__)


	def __init__(self, Objman:ObjManager,
						fleet_name:str,
						fleet_sys: Union[str, None]=None,
						agent_total: Union[int, None]=None):
		
		self.Objman = Objman
		self.fleet = fleet_name
		self.fleet_sys = fleet_sys
		self.inventory = dict()
		self.sdf = [pd.DataFrame()]

		# lookup in DB if there are any ships in fleet
		re_ships_sym = self.get_ships(agent_total)

		err = False

		# init ships
		if len(re_ships_sym) == 0:
			# no ships at all

			# get the agent info for total ships
			# agent just started, need to load the 2 ships in
			if (agent_total is not None and agent_total == 2) or self.api_get_agent_info()["shipCount"] == 2:

				for shippy in self.api_get_all_ships():
					Shippy = self.init_ship(shippy)
					# need to save ship in DB
					if not Shippy.insert_ship(Shippy.jj):
						err = True
						self.__class__._log.error("ShipHandler failed inserting Ship data of '{}.{}'".format(Shippy.name, Shippy.frame))
													
			#not even the ones u get from creating agent	
			else:
				self.__class__._log.critical("ShipHandler failed instantiating any ships to handle")

		else:
			for shippy_sym in re_ships_sym:
				
				bluepr = Ship._get_ship_main_info_col_blueprint()
				bluepr.update({"symbol": shippy_sym})
				# create blank Ship Obj with only sym/name
				Shippy = self.init_ship(bluepr)

		if not err and len(self.inventory) > 0:
			self.__class__._log.info(f"ShipHandler built Fleet '{self.fleet}' with {len(self.inventory)} ships")
			if self.fleet_sys is None:
				self.fleet_sys = list(self.inventory.values())[0].system

			self.__class__._log.info(f"Fleet '{self.fleet}' was asigned system {self.fleet_sys}")

		else:
			self.__class__._log.critical("ShipHandler failed inserting ships into empty DB")


	def get_ships(self, agent_total: Union[int, None]=None) -> list:

		re = self.Objman.sel(f"SELECT symbol FROM ships WHERE fleets_id=?",
								(self.fleet,),
								_format=False)

		fleet_ships_in_db = False
		db_ships = list()

		if len(re) > 0:
			fleet_ships_in_db = True
			db_ships = [i[0] for i in re]

		if agent_total is None:
			# lookup endpoint for ships and add all of them to fleet
			total, api_ships = self.api_get_ships(pages=False)
		else:
			total = agent_total

		# either some ships are missing from DB
		# or some other fleet also has ships
		if total != len(db_ships) and len(db_ships) != 0:
			self.__class__._log.warning(f"Fleet '{self.fleet}' detected more ships exist outside own fleet")

		if fleet_ships_in_db:
			return db_ships

		else:
			self.__class__._log.warning(f"Fleet '{self.fleet}' has no ships in DB")

			return db_ships


	def api_get_agent_info(self) -> dict:
		url = self.Objman.Conf.config["sites"]["SPACETRADERS"]["GET"]["AGENT_INFO"]
		suc, re = self.Objman.get(url=url)

		if suc:
			return re.Response.json()["data"]

		else:
			self.__class__._log.error("api_get_agent_info failed")
			return {"shipCount": None}


	def api_get_all_ships(self) -> list:
		# lookup endpoint for ships and add all of them to fleet
		_, api_ships = self.api_get_ships()

		return api_ships
			

	def api_get_ships(self, pages:bool=True) -> Union[None, int, list]:
		# returns int/None, list
		# int would be the number of total ships, if None, then len(list) gives total
		url = self.Objman.Conf.config["sites"]["SPACETRADERS"]["GET"]["SHIPS_INFO"]
		suc, re = self.Objman.get(url=url)

		if not suc:
			self.__class__._log.error(f"api_get_ships failed to get ships for Fleet '{self.fleet}'")

			return None, list()	

		else:
			# pull into return var data
			re_dec = re.Response.json()
			data = re_dec["data"]

			# if pages is True
			# if it needs more pages, pull them
			# extend data with list coming back
			if (pages and 
				"meta" in re_dec and
				meta.needs_more_pages(re_dec["meta"])):
				data.extend(meta.api_get_pages(self.Objman, url, re_dec, self.__class__._log))

				return None, data

			else:
				return re_dec["meta"]["total"], data


	def update_ships(self):
		pass

	def init_ship(self, ship_data:dict) -> Ship:
		Shippy = Ship(ship_data, self.sdf, self.Objman, self.fleet)

		self.inventory.update({Shippy.name: Shippy})

		return Shippy

	def purchase_ship(self):
		pass

	def sell_ship(self):
		pass

	def get_nearest(self, coord, ship_type):
		pass
		# query from inventory after self.update_ships() which one is nearest to coord
		# also query according to ship_type

	def ship_journey(self, Ship, coord:coord.GameCoord) -> Union[bool, list]:
		pass

		# check if we can refuel here
		if self.refuel_here():
			# check if in range after refuelling here and reducing reserve to 3%
			if (self.fuel < self.fuelCapacity and
				self.in_range(coord, mode=mode, current_fuel=self.fuelCapacity, reserve=0.03)):
			
				self.refuel()

			# we can refuel here, but capacity not enough to go there
			else:
				return False

		# fuel at max capacity, or even if refueled
		# too far away
		else:
			return False
