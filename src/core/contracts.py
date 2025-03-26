# contracts
import time, copy
from typing import Union

from core.waypoints import Waypoint
from core.utils import meta
from core.utils.objmanager import ObjManager
from hkeep.log.logger import get_logger
from utils.sql import strings
from utils.time import ISO_to_epoch, conv_time_time_to_def


class Contract:

	_log = get_logger(__name__)


	@classmethod
	def blueprint(cls) -> dict:

		contract = {
				"sptr_id": None,
				"deadline": None,
				"pay_now": None,
				"pay_fullf": None,
				"fulfilled": None,
				"accepted": None,
				"factions": None,
				"contracts_type": None,
				"expiration": None,
				"accept_deadl": None
		}

		return contract


	@classmethod
	def api_get_contracts(cls, Objman:ObjManager) -> list:
		cls._log.error("api_get_contracts has been called without implementation")


	@classmethod
	def api_get_all_contracts(cls, Objman:ObjManager, check:bool=True) -> list:
		url = Objman.Conf.config["sites"]["SPACETRADERS"]["GET"]["CONTRACTS_INFO"]
		suc, re = Objman.get(url=url)

		if not suc:
			cls._log.error("api_get_all_contracts failed to get contracts")
			return list()

		re_dec = re.Response.json()

		# check how many there are total
		if not "meta" in re_dec:
			cls._log.error("api_get_all_contracts failed to obtain 'meta' on GET request ({})".format(re.Response._reqID))

			re_api = list()
			
			# at least update what we got in response
			if "data" in re_dec:
				# instantiate ctrct in re_dec["data"]
				for ctrct in re_dec["data"]:
					C = cls(Objman, ctrct)
					C.insert_contract()
					re_api.append(C)

			return re_api

		data = list()
		total_ctrct = re_dec["meta"]["total"]

		# check if DB has all
		if check:	
			DB_ctrct = cls.get_all_contracts(Objman)
			if len(DB_ctrct) == total_ctrct:
				return DB_ctrct
				
		else:
			# need to get more from API
			re_api = list()

			# instantiate ctrct in re_dec["data"]
			for ctrct in re_dec["data"]:
				C = cls(Objman, ctrct)
				C.insert_contract()
				re_api.append(C)

			# now use meta to grab if there is more
			if "meta" in re_dec and meta.needs_more_pages(re_dec["meta"]):
				re_dec["data"].extend(meta.api_get_pages(Objman, url, re_dec, cls._log))

				# add the ones not in DB yet
				for ctrct in re_dec["data"]:
					
					C = cls(Objman, ctrct)
					C.insert_contract()
					re_api.append(C)

			return re_api


	@classmethod
	def get_all_contracts(cls, Objman:ObjManager) -> list:

		bluepr = cls.blueprint()
		com = f"SELECT {strings.get_str_sql_sel_cols(bluepr)} FROM contracts;"

		re = Objman.sel(com, _format=False)

		if len(re) == 0:
			cls._log.warning("no contracts found in DB")

			return list()

		contract_list = list()

		for contract_raw in re:	
			
			C = cls(Objman, {})
			C.ctrct_data = C.init_ctrct_data(contract_raw)

			contract_list.append(C)


		return contract_list


	@classmethod
	def get_ctrct_id(cls, Objman:ObjManager, sptr_id:str) -> Union [int, None]:
		# get the id of the table row
		com = f"SELECT id FROM contracts WHERE sptr_id=?;"
		com_var = (sptr_id,)

		ctrct_id = Objman.sel(com, com_var, _format=False)

		if len(ctrct_id) == 0:
			return

		return ctrct_id[0][0]


	def __init__(self, Objman:ObjManager, contract_data:dict):
		self.Objman = Objman
		self.ctrct_data = contract_data


	def __str__(self) -> str:
		wps = {i["destinationSymbol"] for i in self.delivr_goods}
		if len(wps) > 1:	
			goods = [f'{i["unitsRequired"]} {i["tradeSymbol"]} delivery at {i["destinationSymbol"]}' for i in self.delivr_goods]
		else:
			goods = [f'{i["unitsRequired"]} {i["tradeSymbol"]}' for i in self.delivr_goods]

		return f"{self.type} {' '.join(goods)}{'' if len(wps) > 1 else ' delivery at '+wps.pop()}"


	@property
	def sptr_id(self):
		return self.ctrct_data["id"]		# sptr_id

	@property
	def faction(self):
		return self.ctrct_data["factionSymbol"]

	@property
	def type(self):
		return self.ctrct_data["type"]

	@property
	def terms_deadl(self):
		return self.ctrct_data["terms"]["deadline"]

	@property
	def terms_paym_now(self):
		return self.ctrct_data["terms"]["payment"]["onAccepted"]

	@property
	def terms_paym_fullf(self):
		return self.ctrct_data["terms"]["payment"]["onFulfilled"]

	@property
	def delivr_goods(self):
		return self.ctrct_data["terms"]["deliver"]

	@property
	def accepted(self):
		return self.ctrct_data["accepted"]

	@property
	def fullf(self):
		return self.ctrct_data["fulfilled"]

	@property
	def expiration(self):
		return self.ctrct_data["expiration"]

	@property
	def accept_deadl(self):
		return self.ctrct_data["deadlineToAccept"]


	def insert_contract(self) -> bool:

		contract = {
				"sptr_id": self.sptr_id,		# sptr_id
				"deadline": ISO_to_epoch(self.terms_deadl),
				"pay_now": self.terms_paym_now,
				"pay_fullf": self.terms_paym_fullf,
				"fulfilled": int(self.fullf),
				"accepted": int(self.accepted),
				"factions": self.faction,
				"contracts_type": self.type,
				"expiration": ISO_to_epoch(self.expiration),
				"accept_deadl": ISO_to_epoch(self.accept_deadl),
				"updated": int(time.time())
		}

		# check if contract has ctrct_id and exists already in contracts table
		if self.__class__.get_ctrct_id(self.Objman, self.sptr_id) is not None:
			return self.update_contract()

		# insert base contract info
		if not self.Objman.ins("contracts", list(contract.values())):
			self.__class__._log.error("insert_contract failed inserting 'contracts' entry for '{}'".format(contract["sptr_id"]))

			return False

		# get the id of the table row
		re = self.__class__.get_ctrct_id(self.Objman, self.sptr_id)

		if re is None:
			self.__class__._log.error(f"insert_contract failed selecting sptr_id '{self.sptr_id}'")

			return False

		# now insert all the goods needed for this contract
		for good in self.delivr_goods:

			vals = [re, good["tradeSymbol"], good["unitsRequired"], good["unitsFulfilled"], Waypoint.get_wp_id(self.Objman, good["destinationSymbol"]), int(time.time())]

			if not self.Objman.ins("_contract_goods", vals):
				self.__class__._log.error("insert_contract failed inserting a good entry for '{}' of {} {}".format(contract["sptr_id"], good["unitsRequired"], good["tradeSymbol"]))

				return False

		self.__class__._log.info("inserted new Contract %(ctrct_str)s", {"ctrct_str": str(self), "_msg_args": ["arg", "value"]})

		return True


	def select_contract(self) -> dict:

		bluepr = self.__class__.blueprint()

		com = f"SELECT {strings.get_str_sql_sel_cols(bluepr)} FROM contracts WHERE sptr_id=?;"
		com_var = (self.sptr_id,)

		re = self.Objman.sel(com, com_var, _format=False)

		if len(re) == 0:
			self.__class__._log.error(f"select_contract failed selecting sptr_id '{com_var[0]}'")

			return dict()

		re = re[0]

		return self.init_ctrct_data(re)


	def select_goods(self, sptr_id:int, ctrct_id: Union[int, None]=None, error:bool=True) -> list:
		if ctrct_id is None:
			# get the sptr_id of the table row
			ctrct_id = self.__class__.get_ctrct_id(self.Objman, sptr_id)
			
			if ctrct_id is None: 
				self.__class__._log.error(f"select_goods failed selecting from 'contracts' sptr_id '{sptr_id}'")

				return list()

		com = f"SELECT ctrct_id, goods, quantity, quantity_fullf, waypoints_id FROM _contract_goods WHERE ctrct_id=?;"
		com_var = (ctrct_id,)

		goods = self.Objman.sel(com, com_var, _format=False)

		if len(goods) == 0:
			if error:	
				self.__class__._log.error(f"select_goods failed selecting ctrct_id '{ctrct_id}' from 'contracts'")

			return list()

		goods_list = list()

		for good in goods:

			goods_list.append({"tradeSymbol": good[1],
					            "destinationSymbol": Waypoint.get_wp_sym(self.Objman, good[4]),
					            "unitsRequired": good[2],
					            "unitsFulfilled": good[3]})

		return goods_list


	def init_ctrct_data(self, inp:list) -> dict:
		ctrct_data = {}
		ctrct_data["id"] = inp[0]	# sptr_id
		ctrct_data["factionSymbol"] = inp[6]
		ctrct_data["type"] = inp[7]

		ctrct_data["terms"] = {}
		ctrct_data["terms"]["deadline"] = conv_time_time_to_def(inp[1])
		
		ctrct_data["terms"]["payment"] = {}
		ctrct_data["terms"]["payment"]["onAccepted"] = inp[2]
		ctrct_data["terms"]["payment"]["onFulfilled"] = inp[3]
		
		ctrct_data["terms"]["deliver"] = self.select_goods(inp[0])
		
		ctrct_data["accepted"] = inp[5]
		ctrct_data["fulfilled"] = inp[4]
		ctrct_data["expiration"] = conv_time_time_to_def(inp[8])
		ctrct_data["deadlineToAccept"] = conv_time_time_to_def(inp[9])

		return ctrct_data


	def update_contract(self, DB_state: Union[dict, None]=None, check:bool=True) -> bool:

		if check:	
			# check correct DB_state
			if DB_state is None or len(DB_state) == 0:
				DB_state = self.select_contract()

		# in case there is no data in DB
		if DB_state is None or len(DB_state) == 0:
			self.insert_contract()

			return True

		# now we need to compare deliver, accepted, fulfilled

		if self.ctrct_data["terms"]["deliver"] != DB_state["terms"]["deliver"]:

			DB_ctrct_goods_sym_fullf = [(i["tradeSymbol"], i["unitsFulfilled"]) for i in DB_state["terms"]["deliver"]]

			for good in self.ctrct_data["terms"]["deliver"]:

				# maybe all values are the same with DB_ctrct_goods, no change needed
				if (good["tradeSymbol"], good["unitsFulfilled"]) in DB_ctrct_goods_sym_fullf:
					continue

				# good already in there, but unitsFulfilled needs update
				elif good["tradeSymbol"] in (i[0] for i in DB_ctrct_goods_sym_fullf):
					# prepare for DB columns and values
					good_updt = {"quantity_fullf": good["unitsFulfilled"], "updated": int(time.time())}
					
					# need the goods_id from _goods to update the correct good in _contract_goods
					goods_id = self.Objman.sel(f"SELECT id FROM _goods WHERE goods=?;", (good["tradeSymbol"],), _format=False)
					if len(goods_id) == 0:
						self.__class__._log.error("update_contract failed to find id in _goods for '{}'".format(good["tradeSymbol"]))

						return False
					
					# update the good
					if not self.Objman.updt(table="_contract_goods", cols=list(good_updt.keys()), vals=list(good_updt.values()), unique={"ctrct_id": self.sptr_id, "goods_id": goods_id[0][0]}):
						self.__class__._log.error("update_contract failed to update '{}' for '{}' with unitsFulfilled '{}'".format(good["tradeSymbol"], self.sptr_id, good["unitsFulfilled"]))

				else:
					self.__class__._log.error("update_contract identified good '{}' that is not already in '_contract_goods'".format(good["tradeSymbol"]))

		base_updt = {}

		if self.ctrct_data["accepted"] != DB_state["accepted"]:
			base_updt["accepted"] = self.ctrct_data["accepted"]

		if self.ctrct_data["fulfilled"] != DB_state["fulfilled"]:
			base_updt["fulfilled"] = self.ctrct_data["fulfilled"]

		if len(base_updt) > 0:	

			if not self.Objman.updt(table="contracts", cols=list(base_updt.keys()), vals=list(base_updt.values()), unique={"sptr_id": self.sptr_id}):
				self.__class__._log.error("update_contract failed to update Contract sptr_id '{}' ".format(self.sptr_id))

				return False

		return True


	def accept_contract(self) -> bool:
		url = copy.deepcopy(self.Objman.Conf.config["sites"]["SPACETRADERS"]["POST"]["ACCEPT_CONTRACT"])
		url = url.format(contractId=self.sptr_id)

		suc, re = self.Objman.post(url=url)

		if not suc:
			self.__class__._log.error("accept_contract failed to accept %(ctrct_str)s", {"ctrct_str": str(self), "_msg_args": ["arg", "value"]})

			return False

		re_dec = re.Response.json()
		# deep copy to give to update_contract as DB_state
		deepcp = copy.deepcopy(self.ctrct_data)
		self.ctrct_data.update(re_dec["data"]["contract"])

		if not self.update_contract(deepcp):
			self.__class__._log.error("accept_contract failed to update DB with %(ctrct_str)s", {"ctrct_str": str(self), "_msg_args": ["arg", "value"]})

			return False

		self.__class__._log.info("accepted Contract %(ctrct_str)s", {"ctrct_str": str(self), "_msg_args": ["arg", "value"]})

		return True
