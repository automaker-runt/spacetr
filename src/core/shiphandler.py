# shiphandler
import json, time
from functools import partial
from typing import Union

from core.ships import Ship
from core.utils import coord, meta, netw
from core.waypoints import Waypoint
from hkeep.log.logger import get_logger
from utils.time import ISO_to_epoch


class ShipHandler:

	_log = get_logger(__name__)


	def __init__(self, Sess, Conf, SqlHan, fleet_name:str):
		
		# TODO
		# make duplicate modules possible in _ship_modules and _ship_mounts

		self.Sess = Sess
		self.Conf = Conf
		self.SqlHan = SqlHan
		self.fleet = fleet_name
		self.inventory = dict()

		# lookup in DB if there are any ships in fleet
		re_ships_sym = self.get_ships()

		# init ships
		if len(re_ships_sym) == 0:
			# no ships at all

			# get the agent info for total ships
			# agent just started, need to load the 2 ships in
			if self.api_get_agent_info()["shipCount"] == 2:
				err = False

				for shippy in self.api_get_all_ships():
					Shippy = self.init_ship(shippy)
					# need to save ship in DB
					if not Shippy.insert_ship(Shippy.jj):
						err = True
						self.__class__._log.error("ShipHandler failed inserting Ship data of '{}.{}'".format(Shippy.name, Shippy.frame))
										

				if not err:
						self.__class__._log.info("ShipHandler built Fleet '{}' with {} ships".format(fleet_name, len(self.inventory), Shippy.name, Shippy.frame))
			
			#not even the ones u get from creating agent	
			else:
				self.__class__._log.critical("ShipHandler failed finding any ships to handle")

		else:
			for shippy_sym in re_ships_sym:
				
				bluepr = Ship._get_ship_main_info_col_blueprint()
				bluepr.update({"symbol": shippy_sym})
				# create blank Ship Obj with only sym/name
				Shippy = self.init_ship(bluepr)
				# read all ship info
				Shippy.jj = Shippy.select_ship()


		# self.get_wp_sym = partial(Waypoint.get_wp_info, SqlHan)
		# self.get_wp_id = partial(Waypoint.get_wp_id, Sess, Conf, SqlHan)


	def get_ships(self) -> list:

		re = self.SqlHan.sel(f"SELECT symbol FROM ships WHERE fleets_id=?",
								(self.fleet,),
								_format=False)

		fleet_ships_in_db = False
		db_ships = list()

		if len(re) > 0:
			fleet_ships_in_db = True
			db_ships = [i[0] for i in re]

		# lookup endpoint for ships and add all of them to fleet
		total, api_ships = self.api_get_ships(pages=False)

		# either some ships are missing from DB
		# or some other fleet also has ships
		if total != len(db_ships):
			self.__class__._log.warning(f"Fleet '{self.fleet}' detected more ships exist outside own fleet")

		if fleet_ships_in_db:
			return db_ships

		else:
			self.__class__._log.warning(f"Fleet '{self.fleet}' has no ships")

			return db_ships


	def api_get_agent_info(self) -> dict:
		url = self.Conf.config["sites"]["SPACETRADERS"]["GET"]["AGENT_INFO"]
		re = self.Sess.get(url=url)

		if netw.validate_re(re, self.__class__._log.error, "api_get_agent_info failed"):
			return re.Response.json()["data"]

		else:
			return {"shipCount": None}


	def api_get_all_ships(self) -> list:
		# lookup endpoint for ships and add all of them to fleet
		_, api_ships = self.api_get_ships()

		return api_ships
			

	def api_get_ships(self, pages:bool=True) -> Union[None, int, list]:
		# returns int/None, list
		# int would be the number of total ships, if None, then len(list) gives total
		url = self.Conf.config["sites"]["SPACETRADERS"]["GET"]["SHIPS_INFO"]
		re = self.Sess.get(url=url)

		if not netw.validate_re(re, self.__class__._log.error, f"api_get_ships failed to get ships for Fleet '{self.fleet}'"):

			return None, list()	

		else:
			# pull into return var data
			re_dec = re.Response.json()
			data = re_dec["data"]

			# if pages is True
			# if it needs more pages, pull them
			# extend data with list coming back
			if (pages and 
				"meta" in data and
				meta.needs_more_pages(re_dec["meta"])):
				return None, data.extend(Ships.api_get_pages(self.Sess, url, re_dec))
			else:
				return re_dec["meta"]["total"], data

			# # prepare while
			# limit = False
			# page = 0
			# url_p = url+"?page={page}"
			# url = url_p.format(page=2)
			
			# # pull more pages if meta indicates further pages or upping limit
			# while needs_more_pages(re_dec["meta"]):
			# 	# go another cycle
			# 	if not limit and "limit" not in url_p:
			# 		page = 2
			# 		re = self.Sess.get(url=url)
					
			# 		url_p = url_p+"&limit={limit}"

			# 	else:
			# 		if not limit:
			# 			limit = True
			# 			url = url_p.format(page=2, limit=20)

			# 		else:
			# 			page += 1
			# 			url = url_p.format(page=page, limit=20)

			# 		re = self.Sess.get(url=url)

				
			# 	if netw.validate_re(re, f"api_get_ships needs_more_pages failed to get ships for Fleet '{self.fleet}'"):
			# 		re_dec = re.Response.content.decode()
			# 		data.extend(re_dec["data"])
			# 	else:
			# 		break

			# return data


	def update_ships(self):
		pass

	def init_ship(self, ship_data:dict) -> Ship:
		Shippy = Ship(ship_data, self.Sess, self.Conf, self.SqlHan, self.fleet)

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
