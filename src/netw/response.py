# response
#import requests, httpx 			maybe we don't need, maybe we need for exception handling?
import time
import requests, httpx
from typing import Union

from hkeep.error import tb
from hkeep.log.logger import get_logger
from netw.request import Request
from utils.time import wait, ISO_to_epoch
from utils.strings.host import getHost
from utils.strings.response import _log_helper_valid, _log_helper_valid_error
from utils.strings.xxhash import hash, getHash


class Response:

	_log = get_logger(__name__)
	timeout_until = 0
	forbidden = False
	HTTP_REPEAT_INVALIDATION = ("error", "method not allowed", "conflict")


	def __init__(self,
						mode:str,
						url:str,
						Session: Union[requests.Session, httpx.Client, None]=None,
						data:dict=dict(),
						lib:str="req",
						private:bool=False,
						cookies: Union[dict, requests.cookies.RequestsCookieJar, None]=None,
						headers: Union[dict, None]=None,
						HTTP_REPEAT_INVALIDATION: Union[tuple, None]=None
				):
		self.url = url
		self.Session = Session
		self.mode = mode
		self.data = data
		self.invalid_reason = None
		self.lib = lib
		self.attempts = 1
		self.private = private
		self.cookies = cookies
		self.headers = self.prepare_headers(headers)
		self.HTTP_REPEAT_INVALIDATION = HTTP_REPEAT_INVALIDATION if HTTP_REPEAT_INVALIDATION is not None else self.__class__.HTTP_REPEAT_INVALIDATION
		self._respID = None
		self._respID = getHash(self._form_atrib_dict())

		self.Response = None

		# decide which instance to use from
		# Session, requests, httpx
		self._set_getter_instance(lib, Session=Session, by="__init__")

		# now decide which mode to use and "concat" to instance/self.getter
		if self.mode == "get":
			# other stuff

			#self.getter = self.getter.get
			self.get()

		elif self.mode.split()[0] == "post":
			# other stuff?

			# data doesn't have to be given
			self.get()

		else:
			self.__class__._log.error("Response given incorrect argument 'mode'")

			raise Exception("Response given incorrect argument 'mode'")


	def get(self, max_attempts:int=5):

		while self.attempts == 1 or int(time.time()) < self.__class__.timeout_until:

			# # don't wait on first Request
			# if self.invalid_reason is not None:
				# waiting until certain time, due to:
				# - multiple timeouts
				# - rate limited
			wait(self.__class__.timeout_until, interval=1.04)
			if self.__class__.forbidden:
				return

			#print(self.Session.headers)

			self.reset_invalid_reason()
			self.Response = Request(self.getter, self.url, data=self.data, headers=self.headers, jjs=self._form_atrib_dict()).run()

			while not self.valid() and self.attempts < max_attempts:

				# in case of error
				if self.invalid_reason in self.HTTP_REPEAT_INVALIDATION:

					break

				# in case of timeout
				if self.invalid_reason == "timeout":
					self.__class__.timeout_until = int(time.time()) + 10
					self.__class__._log.info(f"get Response timeouted, waiting {self.__class__.timeout_until-int(time.time())}s")
					max_attempts += 1
					self.attempts += 1

					break

				# when we are rate limited, wait some time
				elif self.invalid_reason == "ratelimit":
					if "spacetraders.io" in self.url and "" in self.Response.headers:
						self.__class__.timeout_until = int(ISO_to_epoch(self.Response.headers["x-ratelimit-reset"]))+4**(self.attempts-1)-1
						self.__class__._log.warning(f"rate limit reached for {self.Response.request.headers["host"]}, waiting {self.__class__.timeout_until-int(time.time())}s")
					else:
						self.__class__.timeout_until = (int(time.time()) + 3) +4**(self.attempts-1)-1
						self.__class__._log.warning(f"rate limit reached waiting {self.__class__.timeout_until-int(time.time())}s")

					max_attempts += 1
					self.attempts += 1

					break

				elif self.invalid_reason == "server":
					max_attempts -= 1
					self.attempts += 1
					
					if self.Response.status_code == 502:
						self.__class__.timeout_until = int(time.time())+24+4**(self.attempts-1)-1
						self.__class__._log.error(f"get got Response with invalid_reason 'server' because of 502 Bad Gateway, waiting {self.__class__.timeout_until-int(time.time())}s")

						break

					else:	
						self.__class__._log.info("get got Response with invalid_reason 'server'")
						time.sleep(0.441)
						self.reset_invalid_reason()
						self.Response = Request(self.getter, self.url, data=self.data, headers=self.headers, jjs=self._form_atrib_dict()).run()

				elif self.invalid_reason == "lib":
					if self.Session is not None:
						# let session handle the invalid_reason == "lib"
						self.__class__._log.info(f"get got Response with invalid_reason 'lib' for the Session")
						
						return

					else:
						# reset only once lib
						if self.attempts == 1:	
							next_lib = "hpx" if self.lib == "req" else "req"
							
							# reset the self.getter instance
							if self._set_getter_instance(lib=next_lib, by="get while attempts=1"):
								self.lib = next_lib
							
							self.attempts += 1
							# need to add .get to getter, because mode hasn't been set
							self.reset_invalid_reason()
							self.Response = Request(self.getter, self.url, data=self.data, headers=self.headers, jjs=self._form_atrib_dict()).run()

						elif self.attempts < max_attempts:
							self.attempts += 1
							self.reset_invalid_reason()
							self.Response = Request(self.getter, self.url, data=self.data, headers=self.headers, jjs=self._form_atrib_dict()).run()

						else:
							# just return the Response
							self.__class__._log.error(f"get failed to get valid Response in {self.attempts} attempts")

							return

				elif self.invalid_reason == "sess":
					# let session handle the invalid_reason == "sess"
					self.__class__._log.info(f"get got Response with invalid_reason 'sess'")
						
					return

			if self.invalid_reason in self.HTTP_REPEAT_INVALIDATION or max_attempts == self.attempts or self.valid():
				break		

		return self.Response


	def post(self):
		self.reset_invalid_reason()
		Resp = Request(self.getter, self.url, self.data)

		self.Response = Resp


	def valid(self) -> bool:

		# checking for unknown errors happened in Request
		if hasattr(self.Response, "Error"):
			self.set_invalid_reason("error")
			self.__class__._log.error(_log_helper_valid_error(self, f"valid Error in Request, case"))

			return False

		# need to check for Request timeout and max_tries exhausted
		if hasattr(self.Response, "ReqTimeout"):
			if self.Session is not None:
				self.set_invalid_reason("timeout")
				self.__class__._log.warning(_log_helper_valid_error(self, f"valid Session is not None returns invalid_reason 'timeout', case"))

			else:
				self.set_invalid_reason("timeout")
				self.__class__._log.warning(_log_helper_valid_error(self, f"valid Session is None returns invalid_reason 'timeout', case"))

			return False

		# need to check http status_codes

		# server error
		if self.Response.status_code >= 500 and self.Response.status_code < 600:
			self.set_invalid_reason("server")
			self.__class__._log.warning(_log_helper_valid(self, "valid code 500-599 returns invalid_reason 'server', case"))

			return False

		# forbidden status_code
		elif self.Response.status_code >= 400 and self.Response.status_code < 500:

			# rate limited
			if self.Response.status_code == 429:
				self.set_invalid_reason("ratelimit")
				self.__class__._log.warning("valid code 429 rate limit reached")

				return False

			# 405 method not allowed
			elif self.Response.status_code == 405:
				self.set_invalid_reason("method not allowed")
				self.__class__._log.error(_log_helper_valid(self, "valid Error code 405 method not allowed, case"))

				return False

			# if it is requests instance, should have reason
			elif ((hasattr(self.Response, "reason") and "forbidden" in self.Response.reason.lower()) or
				(hasattr(self.Response, "reason_phrase") and "forbidden" in self.Response.reason_phrase.lower()) or
				self.Response.status_code == 403
				):
				if hasattr(self.Response, "reason_phrase"):
					self.Response.reason = self.Response.reason_phrase

				self.set_invalid_reason("lib")
				self.__class__._log.warning(_log_helper_valid(self, "valid code 400-499 & Session is not None returns invalid_reason 'lib', case"))

				return False

			# if it is requests instance, should have reason
			elif ((hasattr(self.Response, "reason") and "conflict" in self.Response.reason.lower()) or
				(hasattr(self.Response, "reason_phrase") and "conflict" in self.Response.reason_phrase.lower()) or
				self.Response.status_code == 409
				):
				if hasattr(self.Response, "reason_phrase"):
					self.Response.reason = self.Response.reason_phrase

				self.set_invalid_reason("conflict")
				self.__class__._log.warning(_log_helper_valid(self, "valid code 400-499 & Session is not None returns invalid_reason 'lib', case"))

				return False

			# sessions
			elif self.Session is not None:
				self.set_invalid_reason("error")
				self.__class__._log.warning(_log_helper_valid(self, "valid code 400-499 & Session is not None returns invalid_reason 'sess', case"))

				return False

			else:
				# pre needs to have {} so hash can format the string and put there the hash
				self.set_invalid_reason("error")
				pre = hash(">{}< valid code 400-499 & Session is not None unknown case")
				self.__class__._log.error(_log_helper_valid(self, pre))

				raise Exception(pre)

		# success codes mapped to modes
		elif ((self.mode == "get" and self.Response.status_code == 200) or
				(self.mode.split()[0] == "post" and self.Response.status_code in (200, 201))
			):
			# if 200 OK, then self Obj is valid

			return True


	def prepare_headers(self, inp: Union[dict, None]=None) -> dict:
		# prepare headers
		
		# make host key
		headers = dict()
		headers.update({'host': getHost(self.url)})

		# if Session is None
		if self.Session is None:
			headers.update({'Connection': 'close',
							'Accept-Encoding': b'',
							'Accept': '*/*'
				})

		if inp is not None:
			headers.update(inp)

		return headers


	def _set_getter_instance(self, lib:str, Session: Union[requests.Session, httpx.Client, None]=None, by:str='') -> bool:
		# decide which instance to use from
		# Session, requests, httpx
		if Session is not None:
			self.getter = self.Session

		elif lib == "req":
			self.getter = requests

		elif lib == "hpx":
			self.getter = httpx

		else:
			self.__class__._log.error(f"_set_getter_instance given incorrect argument 'lib'{' '+by if len(by)>0 else by} ")

			raise Exception(f"_set_getter_instance given incorrect argument 'lib'{' '+by if len(by)>0 else by} ")

		return True


	def _form_atrib_dict(self) -> dict:
		re_dict = {
					"url": self.url,
					"SID": 0 if self.Session is None else self.Session._SID,
					"mode": self.mode,
					"data": self.data,
					"invalid_reason": self.invalid_reason,
					"lib": self.lib,
					"attempts": self.attempts,
					"private": self.private,
					"cookies": self.cookies,
					"headers": self.headers,
					"respID": self._respID
					}

		return re_dict


	def set_invalid_reason(self, val: Union[None, str]) -> None:

		if not self.invalid_reason == val:
			update = False
			if self.invalid_reason is None:
				update = True

			self.invalid_reason = val
			
			# here we can log the last one if we have _reqID
			if update and hasattr(self.Response, "_reqID"):	
				re = Request.netSH.updt("netmsg", ["invalid_reason"], [self.invalid_reason], unique={"reqID": self.Response._reqID})
				self.__class__._log.debug(f"updt 'netmsg' invalid_reason({self.invalid_reason}): {re}")

	def reset_invalid_reason(self) -> None:
		if self.invalid_reason is not None:
			self.invalid_reason = None


