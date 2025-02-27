# ctrct
# logic for contracts to be selected for PreTask
import time
import threading

from core.contracts import Contract
from core.tasks import PreTask
from core.utils.coord import GameCoord
from core.utils.objmanager import ObjManager
from core.waypoints import Waypoint
from hkeep.log.logger import get_logger
from utils.strings.shorten import short


class ContractLogic:


	_log = get_logger(__name__)


	def __init__(self, Objman:ObjManager, contracts:dict, ev_quit:threading.Event):
		self.Objman = Objman
		self.contracts = contracts
		self.ev_quit = ev_quit
		
		self.history = list()

		self.thr = threading.Thread(target=self.contract_logic, args=(ev_quit,), name='t_ctrct_logi', daemon=False)
		self.thr.start()


	def contract_logic(self, ev_quit:threading.Event):
		last_check = 0

		self.__class__._log.info(f"[{self.thr.name}] instantiated with id {threading.get_ident()}")

		while not ev_quit.is_set():
			
			if int(time.time()) > self.Objman.Conf.config["THREAD_CTRCT_LOGI_API_INTERVAL"] + last_check:
				re_ = Contract.get_all_contracts(self.Objman)
				if len(re_) == 0:
					re_ = Contract.api_get_all_contracts(self.Objman, check=False)

				to_add = dict()

				for ctrct in re_:
					# if not already in there and also not already fullfilled
					if (ctrct.sptr_id not in self.contracts and
						ctrct.sptr_id not in self.history and
						not ctrct.fullf):

						PT = PreTask(ctrct.sptr_id,
										ctrct,
										"contract",
										[Waypoint.get_wp_GameCoord(self.Objman, i["destinationSymbol"]) for i in ctrct.delivr_goods])
						
						to_add[ctrct.sptr_id] = PT
						self.history.append(ctrct.sptr_id)

				if len(to_add) > 0:	
					self.contracts.update(to_add)

				last_check = int(time.time())

			time.sleep(self.Objman.Conf.config["THREAD_CTRCT_LOGI_INTERVAL"])

		# close open DB connections
		if not self.Objman.Sqhlhan.ConnHandler.remove_thr_conns():
			self.__class__._log.error(f"[{self.thr.name}] contract_logic failed closing all thread Connections to DB {short(self.Objman.Sqhlhan.dbfp)}")

		self.__class__._log.info(f"[{self.thr.name}] closed")
