# waypoints
import time
from typing import Union

from core.utils import netw
from hkeep.log.logger import get_logger
from utils.time import ISO_to_epoch

class Waypoint:

	_log = get_logger(__name__)
	inventory = dict()

	@classmethod
	def get_wp_id(cls, Sess, Conf, SqlHan, wp:str) -> Union[int, None]:

		re = SqlHan.sel(f"SELECT id FROM waypoints WHERE wp_symbol=?;", (wp,), _format=False)

		if len(re) > 0:

			return re[0][0]

		else:
			re_api = cls.api_get_wp_info(Sess, Conf, SqlHan, wp)

			# insert waypoint data
			if len(re_api) > 0 and cls.insert_wp(SqlHan, re_api, check=False):
				return cls.get_wp_id(Sess, Conf, SqlHan, wp)

			else:
				cls._log.error(f"get_wp_id failed getting id from waypoint {wp} due to failed result in api_get_wp_info: {re_api}")


	@classmethod
	def api_get_wp_info(cls, Sess, Conf, SqlHan, wp:str) -> dict:
		url = Conf.config["sites"]["SPACETRADERS"]["GET"]["LOCATION_INFO"].format(systemSymbol=wp[:wp.rfind('-')], waypointSymbol=wp)
		re = Sess.get(url=url)
		
		if not netw.validate_re(re, cls._log.critical, f"api_get_wp_info failed to get waypoint {wp}"):
			return dict()

		else:
			re_dec = re.Response.json()

			return re_dec["data"]


	@classmethod
	def get_wp_sym(cls, SqlHan, id_:int) -> Union[int, None]:

		re = SqlHan.sel(f"SELECT wp_symbol FROM waypoints WHERE id=?;", (id_,), _format=False)

		if len(re) > 0:

			return re[0][0]

		else:
			cls._log.error(f"get_wp_sym failed getting wp_symbol from id {id_} because id not in there")

	@classmethod
	def get_wp_sym_short(cls, SqlHan, id_:int) -> Union[int, None]:
		# for origin
    	# re_origin = SptrSH.sel(f"SELECT wp_type, systemsymbol, coords FROM waypoints WHERE wp_symbol=?", (ship_data["nav"]["route"]["origin"]["symbol"],), _format=False)
		pass


	@classmethod
	def insert_wp(cls, SqlHan, data:dict, check:bool=True) -> bool:
		if check:
			re = SqlHan.sel(f"SELECT id FROM waypoints WHERE wp_symbol=?;", (data["symbol"],), _format=False)

			if len(re) > 0:
				return cls.update_wp(SqlHan, data)

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

		if SqlHan.ins("waypoints", list(wp_info.values())):
			# get the id of the waypoint
			wp_id = cls.get_wp_id(None, None, SqlHan, data["symbol"])

			# need to go further with tables for traits, orbitals, modifiers
			error = False

			if len(data["traits"]) > 0:
				if not cls.insert_wp_traits(SqlHan, data["traits"], wp_id):
					error = True
			if len(data["orbitals"]) > 0:
				if not cls.insert_wp_orbitals(SqlHan, data["orbitals"], wp_id):
					error = True
			if len(data["modifiers"]) > 0:
				if not cls.insert_wp_modifiers(SqlHan, data["modifiers"], wp_id):
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
	def update_wp(cls, SqlHan, data:dict) -> bool:
		pass

	@classmethod
	def insert_wp_traits(cls, SqlHan, traits_data:list, wp_sym_id:str) -> bool:
		for trait in traits_data:
			
			com = f"SELECT id FROM traits WHERE symbol=?;"
			com_var = (trait["symbol"],)

			re = SqlHan.sel(com, com_var, _format=False)

			# check if trait exists
			if len(re) == 0:
				# append time for updated column
				vals = list(trait.values())
				vals.append(int(time.time()))

				# add new trait
				if SqlHan.ins("traits", vals):
					cls._log.info("new waypoint trait '{}' added".format(trait["symbol"]))

					# now get it's id
					re = SqlHan.sel(com, com_var, _format=False)
					trait_id = re[0][0]

					# insert linked waypoint symbol with the traid id
					if not SqlHan.ins("_wp_traits", [wp_sym_id, trait_id]):
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
				re = SqlHan.sel(com, com_var, _format=False)

				if len(re) == 0:
					if not SqlHan.ins("_wp_traits", [wp_sym_id, trait_id]):
						cls._log.error(f"insert_wp_traits failed after trait already known insert in '_wp_traits': {[wp_sym_id, trait_id]}")
						
						return False

		return True


	@classmethod
	def insert_wp_orbitals(cls, SqlHan, orbitals_data:list, wp_sym_id:str) -> bool:
		for orbital in orbitals_data:
			
			com = f"SELECT id FROM orbitals WHERE symbol=?;"
			com_var = (orbital["symbol"],)

			re = SqlHan.sel(com, com_var, _format=False)

			# check if orbital exists
			if len(re) == 0:
				# append time for updated column
				vals = list(orbital.values())
				vals.append(int(time.time()))

				# add new orbital
				if SqlHan.ins("orbitals", vals):
					cls._log.info("new waypoint orbital '{}' added".format(orbital["symbol"]))

					# now get it's id
					re = SqlHan.sel(com, com_var, _format=False)
					orbital_id = re[0][0]

					# insert linked waypoint symbol with the orbital id
					if not SqlHan.ins("_wp_orbitals", [wp_sym_id, orbital_id]):
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
				re = SqlHan.sel(com, com_var, _format=False)

				if len(re) == 0:
					if not SqlHan.ins("_wp_orbitals", [wp_sym_id, orbital_id]):
						cls._log.error(f"insert_wp_orbitals failed after orbital already known insert in '_wp_orbitals': {[wp_sym_id, orbital_id]}")
						
						return False

		return True


	@classmethod
	def insert_wp_modifiers(cls, SqlHan, modifiers_data:list, wp_sym_id:str) -> bool:
		for modifier in modifiers_data:
			
			com = f"SELECT id FROM modifiers WHERE symbol=?;"
			com_var = (modifier["symbol"],)

			re = SqlHan.sel(com, com_var, _format=False)

			# check if modifier exists
			if len(re) == 0:
				# append time for updated column
				vals = list(modifier.values())
				vals.append(int(time.time()))

				# add new modifier
				if SqlHan.ins("modifiers", vals):
					cls._log.info("new waypoint modifier '{}' added".format(modifier["symbol"]))

					# now get it's id
					re = SqlHan.sel(com, com_var, _format=False)
					modifier_id = re[0][0]

					# insert linked waypoint symbol with the modifier id
					if not SqlHan.ins("_wp_modifiers", [wp_sym_id, modifier_id]):
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
				re = SqlHan.sel(com, com_var, _format=False)

				if len(re) == 0:
					if not SqlHan.ins("_wp_modifiers", [wp_sym_id, modifier_id]):
						cls._log.error(f"insert_wp_modifiers failed after modifier already known insert in '_wp_modifiers': {[wp_sym_id, modifier_id]}")
						
						return False

		return True

