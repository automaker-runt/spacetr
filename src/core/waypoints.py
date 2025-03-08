# waypoints
import time
import pandas as pd
from typing import Union

from core.utils import coord, meta, netw
from core.utils.coord import GameCoord
from core.utils.objmanager import ObjManager
from hkeep.log.logger import get_logger
from utils.time import ISO_to_epoch

class Waypoint:

	_log = get_logger(__name__)
	inventory = dict()

	@classmethod
	def get_wp_GameCoord(cls, Objman:ObjManager, wp:str) -> Union [GameCoord, None]:
		re = Objman.sel(f"SELECT coords FROM waypoints WHERE wp_symbol=?;", (wp,), _format=False)

		Gamecoord = None

		if len(re) == 0:
			for wayp in cls.api_get_all_sys_wp(Objman, wp):
				cls.insert_wp(Objman, wayp)
				if wayp["symbol"] == wp:
					Gamecoord = GameCoord(wayp["x"], wayp["y"], wp)

		else:
			Gamecoord = GameCoord(*re[0][0].split('::'), wp)

		if Gamecoord is not None:
			return Gamecoord
		else:
			cls._log.error(f"get_wp_GameCoord ended with Gamecoord of None for wp '{wp}'")


	@classmethod
	def get_wp_id(cls, Objman:ObjManager, wp:str) -> Union[int, None]:

		re = Objman.sel(f"SELECT id FROM waypoints WHERE wp_symbol=?;", (wp,), _format=False)

		if len(re) > 0:

			return re[0][0]

		else:
			re_api = cls.api_get_wp_info(Objman, wp)

			# insert waypoint data
			if len(re_api) > 0 and cls.insert_wp(Objman, re_api, check=False):
				return cls.get_wp_id(Objman, wp)

			else:
				cls._log.error(f"get_wp_id failed getting id from waypoint {wp} due to failed result in api_get_wp_info: {re_api}")


	@classmethod
	def api_get_wp_info(cls, Objman, wp:str) -> dict:
		# returns whole wp dictionary from api

		url = Objman.Conf.config["sites"]["SPACETRADERS"]["GET"]["LOCATION_INFO"].format(systemSymbol=wp[:wp.rfind('-')], waypointSymbol=wp)
		suc, re = Objman.get(url=url)
		
		if not suc: 
			cls._log.critical(f"api_get_wp_info failed to get waypoint {wp}")
			return dict()

		else:
			re_dec = re.Response.json()

			return re_dec["data"]


	@classmethod
	def get_wp_sym(cls, Objman:ObjManager, id_:int) -> Union[int, None]:

		re = Objman.sel(f"SELECT wp_symbol FROM waypoints WHERE id=?;", (id_,), _format=False)

		if len(re) > 0:

			return re[0][0]

		else:
			cls._log.error(f"get_wp_sym failed getting wp_symbol from id {id_} because id not in there")

	@classmethod
	def get_wp_sym_short(cls, Objman:ObjManager, id_:int) -> Union[int, None]:
		cls._log.error("get_wp_sym_short has been called without implementation")


	@classmethod
	def insert_wp(cls, Objman:ObjManager, data:dict, check:bool=True) -> bool:
		if check:
			re = Objman.sel(f"SELECT id FROM waypoints WHERE wp_symbol=?;", (data["symbol"],), _format=False)

			if len(re) > 0:
				return cls.update_wp(Objman, data)

		wp_info = {

					"wp_symbol": data["symbol"],
					"wp_type": data["type"],
					"systemsymbol": data["systemSymbol"],
					"coords": f'{data["x"]}::{data["y"]}',
					"factions": data["faction"]["symbol"],
					"isUnderConstruction": 0 if data["isUnderConstruction"] == False else 1,
					"chart_by": data["chart"]["submittedBy"],
					"chart_time": ISO_to_epoch(data["chart"]["submittedOn"]),
					"orbits": None,
					"updated": int(time.time())
		}

		if Objman.ins("waypoints", list(wp_info.values())):
			# get the id of the waypoint
			wp_id = cls.get_wp_id(Objman, data["symbol"])

			# need to go further with tables for traits, orbitals, modifiers
			error = False

			if len(data["traits"]) > 0:
				if not cls.insert_wp_traits(Objman, data["traits"], wp_id):
					error = True
			if len(data["orbitals"]) > 0:
				if not cls.insert_wp_orbitals(Objman, data["orbitals"], wp_id):
					error = True
			if len(data["modifiers"]) > 0:
				if not cls.insert_wp_modifiers(Objman, data["modifiers"], wp_id):
					error = True

			if not error:
				cls._log.info("new waypoint '{}_{}' added".format(wp_info["wp_symbol"], wp_info["coords"]))
				return True
			else:
				cls._log.error("insert_wp failed inserting traits, orbitals or modifiers after adding new waypoint '{}_{}' ".format(wp_info["wp_symbol"], wp_info["coords"]))
				return False

		else:
			cls._log.error("insert_wp failed inserting 'waypoints' entry for {} with: {}".format(wp_info["wp_symbol"], list(wp_info.values())))

			return False


	@classmethod
	def update_wp(cls, Objman:ObjManager, data:dict) -> bool:
		# TODO needs implementation
		cls._log.error("update_wp got called and isn't implemented")

		return True

	@classmethod
	def insert_wp_traits(cls, Objman:ObjManager, traits_data:list, wp_sym_id:str) -> bool:
		for trait in traits_data:
			
			com = f"SELECT id FROM traits WHERE symbol=?;"
			com_var = (trait["symbol"],)

			re = Objman.sel(com, com_var, _format=False)

			# check if trait exists
			if len(re) == 0:
				# append time for updated column
				vals = list(trait.values())
				vals.append(int(time.time()))

				# add new trait
				if Objman.ins("traits", vals):
					cls._log.info("new waypoint trait '{}' added".format(trait["symbol"]))

					# now get it's id
					re = Objman.sel(com, com_var, _format=False)
					trait_id = re[0][0]

					# insert linked waypoint symbol with the traid id
					if not Objman.ins("_wp_traits", [wp_sym_id, trait_id]):
						cls._log.error(f"insert_wp_traits failed insert in '_wp_traits': {[wp_sym_id, trait_id]}")
						
						return False

				else:
					cls._log.error(f"insert_wp_traits failed insert in 'traits': {vals}")
					
					return False

			# we got the trait id
			else:
				trait_id = re[0][0]

				com = f"SELECT * FROM _wp_traits WHERE wp_symbol_id=? AND traits_id=?;"
				com_var = (wp_sym_id, trait_id)

				# check if trait isn't already linked to waypoint symbol for some reason...
				re = Objman.sel(com, com_var, _format=False)

				if len(re) == 0:
					if not Objman.ins("_wp_traits", [wp_sym_id, trait_id]):
						cls._log.error(f"insert_wp_traits failed after trait already known insert in '_wp_traits': {[wp_sym_id, trait_id]}")
						
						return False

		return True


	@classmethod
	def insert_wp_orbitals(cls, Objman, orbitals_data:list, wp_sym_id:str) -> bool:
		for orbital in orbitals_data:
			
			com = f"SELECT id FROM orbitals WHERE symbol=?;"
			com_var = (orbital["symbol"],)

			re = Objman.sel(com, com_var, _format=False)

			# check if orbital exists
			if len(re) == 0:
				# append time for updated column
				vals = list(orbital.values())
				vals.append(int(time.time()))

				# add new orbital
				if Objman.ins("orbitals", vals):
					cls._log.info("new waypoint orbital '{}' added".format(orbital["symbol"]))

					# now get it's id
					re = Objman.sel(com, com_var, _format=False)
					orbital_id = re[0][0]

					# insert linked waypoint symbol with the orbital id
					if not Objman.ins("_wp_orbitals", [wp_sym_id, orbital_id]):
						cls._log.error(f"insert_wp_orbitals failed insert in '_wp_orbitals': {[wp_sym_id, orbital_id]}")
						
						return False

				else:
					cls._log.error(f"insert_wp_orbitals failed insert in 'orbitals': {vals}")
					
					return False

			# we got the orbital id
			else:
				orbital_id = re[0][0]

				com = f"SELECT * FROM _wp_orbitals WHERE wp_symbol_id=? AND orbitals_id=?;"
				com_var = (wp_sym_id, orbital_id)

				# check if orbital isn't already linked to waypoint symbol for some reason...
				re = Objman.sel(com, com_var, _format=False)

				if len(re) == 0:
					if not Objman.ins("_wp_orbitals", [wp_sym_id, orbital_id]):
						cls._log.error(f"insert_wp_orbitals failed after orbital already known insert in '_wp_orbitals': {[wp_sym_id, orbital_id]}")
						
						return False

		return True


	@classmethod
	def insert_wp_modifiers(cls, Objman:ObjManager, modifiers_data:list, wp_sym_id:str) -> bool:
		for modifier in modifiers_data:
			
			com = f"SELECT id FROM modifiers WHERE symbol=?;"
			com_var = (modifier["symbol"],)

			re = Objman.sel(com, com_var, _format=False)

			# check if modifier exists
			if len(re) == 0:
				# append time for updated column
				vals = list(modifier.values())
				vals.append(int(time.time()))

				# add new modifier
				if Objman.ins("modifiers", vals):
					cls._log.info("new waypoint modifier '{}' added".format(modifier["symbol"]))

					# now get it's id
					re = Objman.sel(com, com_var, _format=False)
					modifier_id = re[0][0]

					# insert linked waypoint symbol with the modifier id
					if not Objman.ins("_wp_modifiers", [wp_sym_id, modifier_id]):
						cls._log.error(f"insert_wp_modifiers failed insert in '_wp_modifiers': {[wp_sym_id, modifier_id]}")
						
						return False

				else:
					cls._log.error(f"insert_wp_modifiers failed insert in 'modifiers': {vals}")
					
					return False

			# we got the modifier id
			else:
				modifier_id = re[0][0]

				com = f"SELECT * FROM _wp_modifiers WHERE wp_symbol_id=? AND modifiers_id=?;"
				com_var = (wp_sym_id, modifier_id)

				# check if modifier isn't already linked to waypoint symbol for some reason...
				re = Objman.sel(com, com_var, _format=False)

				if len(re) == 0:
					if not Objman.ins("_wp_modifiers", [wp_sym_id, modifier_id]):
						cls._log.error(f"insert_wp_modifiers failed after modifier already known insert in '_wp_modifiers': {[wp_sym_id, modifier_id]}")
						
						return False

		return True


	@classmethod
	def api_get_all_sys_wp(cls, Objman:ObjManager, sys_wp:str) -> list:
		# returns list with GameCoord Obj for every wp

		url = Objman.Conf.config["sites"]["SPACETRADERS"]["GET"]["WAYPOINTS"].format(systemSymbol=sys_wp)
		suc, re = Objman.get(url=url)


		if not suc:
			cls._log.error(f"api_get_all_sys_wp failed to get system '{sys_wp}' waypoints")
			return list()

		else:
			data = list()

			re_dec = re.Response.json()

			# check how many there are total
			if not "meta" in re_dec:
				cls._log.error("api_get_all_sys_wp failed to obtain 'meta' on GET request ({})".format(re.Response._reqID))

				return list()
			
			total_wp = re_dec["meta"]["total"]

			# get all wp from DB
			re_DB = Objman.sel(f"SELECT wp_symbol, coords FROM waypoints WHERE wp_symbol LIKE '{sys_wp}%'", _format=False)

			# rerank symbols to top level out of their tuples
			# add the corresponding coords as GameCoord to re_coords
			re_coords = list()
			re_DB = [i[0] for i in re_DB if re_coords.append(coord.GameCoord(*i[1].split('::'), i[0])) is None]

			# DB has all maybe
			if len(re_DB) == total_wp:
				return re_coords
			
			elif len(re_DB) > total_wp:	
				cls._log.error(f"api_get_all_sys_wp detected more waypoints in DB in system '{sys_wp}' than the total the API provides: {len(re_DB)} > {total_wp}")

			else:
				re_api = list()

				if "meta" in re_dec and meta.needs_more_pages(re_dec["meta"]):
					re_dec["data"].extend(meta.api_get_pages(Objman, url, re_dec, cls._log))

					# add the ones not in DB yet
					for wp in re_dec["data"]:
						if not wp["symbol"] in re_DB:
							if not cls.insert_wp(Objman, data=wp, check=False):
								cls._log.error("api_get_all_sys_wp failed insert new wp '{}'".format(wp["symbol"]))

							re_api.append(wp["symbol"])
							re_coords.append(coord.GameCoord(wp["x"], wp["y"], wp["symbol"]))


			return re_coords


	@classmethod
	def get_sys_wp_df(cls, Objman:ObjManager, sys_wp:str) -> pd.core.frame.DataFrame:
		re_DB = Objman.sel(f"SELECT * FROM waypoints_trts_orbtl_mdf_view WHERE wp_symbol LIKE '{sys_wp}%'", _format=False)

		if len(re_DB) == 0:
			# trigger Waypoint insert
			Waypoint.api_get_all_sys_wp(Objman, sys_wp)
			re_DB = Objman.sel(f"SELECT * FROM waypoints_trts_orbtl_mdf_view WHERE wp_symbol LIKE '{sys_wp}%'", _format=False)

			if len(re_DB) == 0:
				cls._log.critical(f"get_sdf_sys_wp failed getting system waypoints from DB after calling api_get_all_sys_wp for system '{sys_wp}'")
				return pd.DataFrame()

		cols = ["id", "wp_symbol", "wp_type", "coords", "traits", "orbitals", "modifiers", "isUnderConstruction", "chart_by", "chart_time", "updated"]

		df = pd.DataFrame(re_DB, columns=cols).set_index("id")
		
		# from https://stackoverflow.com/a/52854800
		def GM(coords, wp):
			return GameCoord(*coords.split('::'), wp)

		df["GmCrd"] = df.apply(lambda x: GM(x.coords, x.wp_symbol), axis=1)		

		return df


	@classmethod
	def validate_wp_sym(cls, Objman:ObjManager, inp: Union[str, list]) -> bool:
		if isinstance(inp, str):
			inp = [inp]

		if None in inp:
			return False
		elif len(inp) == 0:
			return False

		return True
