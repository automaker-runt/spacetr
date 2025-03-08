# objectmanager
import time, sys
from threading import Event
from typing import Union

from core.utils import netw
from handler.sql import SqlHand
from hkeep.log.logger import get_logger
from netw.httpsession import HttpSession
from netw.response import Response
from settings.settings import Config
from utils.strings import uptick


class ObjManager:
	# takes in and wraps HttpSession, SqlHand, Config Objects
	# manages them as an Interface to core classes
	# changes them if needed by core, to seamlessly continue
	# giving use to core classes of managed Objects

	# self detects resets in spacetraders and reconfigs SqlHand

	_log = get_logger(__name__)
	_is_fresh_reset_procedure_active = False

	
	@classmethod
	def is_fresh_reset(cls, resp: Union[Response, None]) -> bool:
		if resp is None:
			return False

		elif hasattr(resp, "Response"):
			if hasattr(resp.Response, "reason_phrase"):
				reason = resp.Response.reason_phrase
			elif hasattr(resp.Response, "reason"):
				reason = resp.Response.reason
			else:
				cls._log.error("is_fresh_reset failed due to not nominal condition met #1")

				return False

		else:
			return False

		if (reason == "Unauthorized" and resp.Response.status_code == 401 or
			(reason == "Conflict" and resp.Response.status_code == 409 and resp.Response.json()["error"]["code"] == 4107)):
			cls._log.info("Fresh reset detected")
			cls._is_fresh_reset_procedure_active = True

			return True


	def __init__(self,
						Netwsess: HttpSession,
						Sqhlhan: SqlHand,
						Conf: Config,
						core_stop_ev: Event,
						core_stopped_ev: Event):

		self.Sqhlhan = Sqhlhan
		self.Netwsess = Netwsess
		self.Conf = Conf
		self.core_stop_ev = core_stop_ev
		self.core_stopped_ev = core_stopped_ev

		self.Agent = None

		self.is_fresh_reset = False


	def sel(self, *args, **kwargs):
		re = self.Sqhlhan.sel(*args, **kwargs)

		return re

	
	def ins(self, *args, **kwargs):
		re = self.Sqhlhan.ins(*args, **kwargs)

		return re

	
	def updt(self, *args, **kwargs):
		re = self.Sqhlhan.updt(*args, **kwargs)

		return re

	
	def get(self, *args, **kwargs):
		re = self.Netwsess.get(*args, **kwargs)
		
		return self.check_re(re), re

	
	def post(self, *args, **kwargs):
		re = self.Netwsess.post(*args, **kwargs)
		
		return self.check_re(re), re


	def check_re(self, re:Response) -> bool:
		result = True

		if not netw.validate_re(re, None, None):
			result = False

			if (not self.__class__._is_fresh_reset_procedure_active and
				self.__class__.is_fresh_reset(re)):
				'''
				blocks outgoing traffic, closes all threads
				creates new DB
				unstucks the thread which triggered this
				'''

				# setting here for t_core to run register_new_agent
				self.is_fresh_reset = True
				self.__class__._is_fresh_reset_procedure_active = True
				# set cooldown on Response class
				# so no Response is run anymore
				is_fresh_reset_timeout = int(time.time())+6000
				Response.timeout_until = is_fresh_reset_timeout
				Response.forbidden = True

				# need to stop all activity for the DB
				# let the threads close their Conn to DB
				self.core_stop_ev.set()
				# core_stopped_ev is being set by t_core right from beginning to
				# prevent deadlock, because t_core waits for Objman to return get
				while not self.core_stopped_ev.is_set():	
					time.sleep(0.5)

				self.core_stop_ev.clear()
				# now we can expect all threads closed (hopefully)
				# we can reset DB to start fresh
				self.Sqhlhan.new_dbfp(uptick.file_in_folder(self.Sqhlhan.dbfp))
				# set new DB path in config, too
				# determine whether PROD env or not
				self.Conf.config["DB_SPACETR_FP_PROD" if any("prod" == i.lower() for i in sys.argv) else "DB_SPACETR_FP"] = self.Sqhlhan.dbfp

				# take out general Response.timeout_until
				if Response.timeout_until == is_fresh_reset_timeout:
					Response.timeout_until = int(time.time())

				self.__class__._is_fresh_reset_procedure_active = False

		return result
