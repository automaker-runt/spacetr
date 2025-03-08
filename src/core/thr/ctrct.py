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
from utils.strings.xxhash import getPureHash


class ContractLogic:


	_log = get_logger(__name__)


	def __init__(self, Objman:ObjManager, ev_quit:threading.Event):
		self.Objman = Objman
		self.ev_quit = ev_quit
		
		self.history = list()

		self.thr = threading.Thread(target=self.contract_logic, args=(ev_quit,), name='t_ctrct_logi', daemon=False)
		self.thr.start()


	def contract_logic(self, ev_quit:threading.Event):
		last_check = 0
		PTid = lambda sptr_id, ctrct_dict: getPureHash(sptr_id+ctrct_dict["tradeSymbol"]+str(ctrct_dict["unitsRequired"]))

		self.__class__._log.info("[{}] instantiated with id %(threadID)s".format(self.thr.name), {"threadID": threading.get_ident(), "_msg_args": ["arg", "value"]})

		while not ev_quit.is_set():
			
			if int(time.time()) > self.Objman.Conf.config["THREAD_CTRCT_LOGI_API_INTERVAL"] + last_check:
				re_ = Contract.get_all_contracts(self.Objman)
				if len(re_) == 0:
					re_ = Contract.api_get_all_contracts(self.Objman, check=False)

				for Ctrct in re_:
					# if not already in there and also not already fullfilled
					if (not Ctrct.fullf and
						any(PTid(Ctrct.sptr_id, i) not in self.history for i in Ctrct.delivr_goods)):

						if not Ctrct.accepted and not Ctrct.accept_contract():
							continue

						for good_PreTask in Ctrct.delivr_goods:
							# multiple goods can have same destination, sptr_id+good is better primary key
							hash_id = PTid(Ctrct.sptr_id, good_PreTask)
							if hash_id not in self.history:

								# rare case where get_wp_GameCoord return None needs filtering
								# to prevent creating PreTask
								wp = Waypoint.get_wp_GameCoord(self.Objman, good_PreTask["destinationSymbol"])
								if wp is not None:
									
									PT = PreTask(self.Objman,
													hash_id,
													Ctrct,
													"contract",
													sys=wp.wp[:wp.wp.rfind('-')],
													GmCrd_dict={"deliver": wp},
													extras={"good": good_PreTask})
							
									# PT adds itself to PreTask.PT_list
									# self.history keeps track to not create multiple
									# PreTasks
									self.history.append(hash_id)

								else:
									self.__class__._log.error("contract_logic Contract %(ctrct_str)s has destinationSymbol '{}' that returns None from get_wp_GameCoord".format(good_PreTask["destinationSymbol"]),
																{"ctrct_str": str(Ctrct), "_msg_args": ["arg", "value"]})

				last_check = int(time.time())

			time.sleep(self.Objman.Conf.config["THREAD_CTRCT_LOGI_INTERVAL"])

		# close open DB connections
		if not self.Objman.Sqhlhan.ConnHandler.remove_thr_conns():
			self.__class__._log.error(f"[{self.thr.name}] contract_logic failed closing all thread Connections to DB {short(self.Objman.Sqhlhan.dbfp)}")

		self.__class__._log.info(f"[{self.thr.name}] closed")
