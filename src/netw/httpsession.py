# HttpSession

import requests, httpx
import time, queue
from typing import Union

from hkeep.error import tb
from hkeep.log.logger import get_logger
from netw.ratelimiter import RateLimiter
from netw.request import Request
from netw.response import Response
from settings.settings import Config
from utils.os_type import OS
from utils.strings.xxhash import hash
from version import __version__


class HttpSession:

	Config = None
	_log = get_logger(__name__)

	HTTP_REPEAT_INVALIDATION = ("error", "method not allowed", "conflict")
	MAX_ATTEMPT_LIB = 2
	MAX_ATTEMPT_SESS = 2
	sessr_num = 0
	sessh_num = 0
	url_lib = dict()


	@classmethod
	def setConfig(cls, Conf:Config) -> None:
		cls.Config = Conf
		if "DEFAULT_SESSION_MAX_ATTEMPT_LIB" in cls.Config.config:
			cls.MAX_ATTEMPT_LIB = cls.Config.config["DEFAULT_SESSION_MAX_ATTEMPT_LIB"]

		if "DEFAULT_SESSION_MAX_ATTEMPT_SESS" in cls.Config.config:
			cls.MAX_ATTEMPT_SESS = cls.Config.config["DEFAULT_SESSION_MAX_ATTEMPT_SESS"]

		if "HTTP_REPEAT_INVALIDATION" in cls.Config.config:
			cls.HTTP_REPEAT_INVALIDATION = cls.Config.config["HTTP_REPEAT_INVALIDATION"]


	def __init__(self, private:bool=False) -> None:
		
		self.private = private
		self.auth_headers = dict()
		self.Ratelimiter = None

		# set self.SessR, self.SessR.headers, self.SessR._SID
		re = self.setSession('req')
		assert re, "setSession('req') didn't return True"
		# set self.SessH, self.SessH.headers, self.SessH._SID
		re = self.setSession('hpx')
		assert re, "setSession('hpx') didn't return True"


	def setSession(self, lib:str) -> bool:

		# check argument lib
		if not isinstance(lib, str) or lib not in ("req", "hpx"):
			pre = hash(">{}< Session lib argument not valid, type:str & in ('req', 'hpx')")
			self.__class__._log.error(pre)

			raise TypeError(pre)

		# setup Session
		elif lib == "req":
			self.__class__.sessr_num += 1
			
			if hasattr(self, "SessR"):
				self.SessR.close()
				self.__class__._log.info("requests Session with _SID '%(SessR_SID)s' closed", {"SessR_SID": self.SessR._SID, "_msg_args": ["arg", "value"]})
			
			self.SessR = requests.Session()
			self.SessR._SID = f"{OS[0]}{__version__}_{lib}{self.__class__.sessr_num}_{int(time.time())}"

			self._set_headers(self.SessR)
			if not self.private:
				self.SessR.headers['User-Agent'] = f'python-requests/{requests.__version__}'

			self.__class__._log.info("requests Session instantiated with _SID '%(SessR_SID)s'", {"SessR_SID": self.SessR._SID, "_msg_args": ["arg", "value"]})
		
		elif lib == "hpx":
			self.__class__.sessh_num += 1
			
			if hasattr(self, "SessH"):
				self.SessH.close()
				self.__class__._log.info("httpx Session with _SID '%(SessH_SID)s' closed", {"SessH_SID": self.SessH._SID, "_msg_args": ["arg", "value"]})

			self.SessH = httpx.Client(http2=True)
			self.SessH._SID = f"{OS[0]}{__version__}_{lib}{self.__class__.sessh_num}_{int(time.time())}"

			self._set_headers(self.SessH)
			if not self.private:
				self.SessH.headers['User-Agent'] = f'python-httpx/{httpx.__version__}'

			self.__class__._log.info("httpx Session instantiated with _SID '%(SessH_SID)s'", {"SessH_SID": self.SessH._SID, "_msg_args": ["arg", "value"]})
		
		else:
			return False
		

		return True


	def get(self, url:str, lib:str="req", headers: Union[dict, None]=None, attempt_lib:int=1, attempt_sess:int=1) -> Response:

		if self.Ratelimiter is not None:	
			self.Ratelimiter.get()

		return self._http_req(
								url=url,
								data={},
								mode="get",
								lib=lib,
								headers=headers,
				)


	def post(self, url:str, data:dict, mode="data", lib:str="req", headers: Union[dict, None]=None, attempt_lib:int=1, attempt_sess:int=1) -> Response:

		if self.Ratelimiter is not None:	
			self.Ratelimiter.get()
			
		return self._http_req(
								url=url,
								data=data,
								mode=f"post {mode}",
								lib=lib,
								headers=headers,
				)

	
	def _http_req(self, 
						url:str, 
						data:dict, 
						mode="data", 
						lib:str="req", 
						headers: Union[dict, None]=None, 
						attempt_lib:int=1, 
						attempt_sess:int=1
				) -> Response:
		'''
		validate Response
		decide:	- reset Session
				- change lib
		'''
		
		# if first attempt and url has been used successfully in past
		# set lib according to self.__class__.url_lib
		# if attempt_lib == 1 and url in self.__class__.url_lib:
		# 	lib = self.__class__.url_lib[url]
		
		# apply self.auth_headers tp headers
		headers = self.apply_auth(url, headers)

		if lib == "req":
			Resp = Response(mode, url, 
											data=data, 
											lib="req",
											Session=self.SessR,
											headers=headers,
											HTTP_REPEAT_INVALIDATION=self.__class__.HTTP_REPEAT_INVALIDATION)
			untried = "hpx"
		
		elif lib == "hpx":
			Resp = Response(mode, url,
											data=data,
											lib="hpx",
											Session=self.SessH, 
											headers=headers,
											HTTP_REPEAT_INVALIDATION=self.__class__.HTTP_REPEAT_INVALIDATION)
			untried = "req"

		else:
			self.__class__._log.error(f"Session given unknown 'lib' value: '{lib}'")

			raise ValueError(f"Session given unknown 'lib' value: '{lib}'")


		if Resp.invalid_reason not in self.__class__.HTTP_REPEAT_INVALIDATION and not Resp.valid():
			if Resp.invalid_reason is not None:
				# could reset Session
				if Resp.invalid_reason == "sess" and attempt_sess < self.__class__.MAX_ATTEMPT_SESS:
					self.setSession(lib)

					return self.post(url, mode=mode, data=data, lib=lib, attempt_lib=attempt_lib, attempt_sess=attempt_sess+1)

				# could change lib
				if Resp.invalid_reason == "lib" and attempt_lib < self.__class__.MAX_ATTEMPT_LIB:

					return self.post(url, mode=mode, data=data, lib=untried, attempt_lib=attempt_lib+1, attempt_sess=attempt_sess)

				return Resp

			else:
				# pre needs to have {} so hash can format the string and put there the hash
				pre = hash(">{}< post returned invalid Response with None 'invalid_reason'")
				self.__class__._log.error(f"{pre}, data={data}")

				raise Exception(f"{pre}")

		else:
			if Resp.invalid_reason not in self.__class__.HTTP_REPEAT_INVALIDATION:
				# success, set the lib used for url
				if attempt_lib > 1 or not url in self.__class__.url_lib:
					self.__class__.url_lib.update({url: lib})

			return Resp


	def _set_headers(self, Sess_Obj) -> None:
		if OS == "Linux":
			if not self.private:
				Sess_Obj.headers = self.__class__.Config.config["DEFAULT_SESSION_HEADERS_LINUX"].copy()
			else:
				Sess_Obj.headers = self.__class__.Config.config["DEFAULT_SESSION_HEADERS_LINUX_PRIV"].copy()
		else:
			if not self.private:
				Sess_Obj.headers = self.__class__.Config.config["DEFAULT_SESSION_HEADERS_WIN"].copy()
			else:
				Sess_Obj.headers = self.__class__.Config.config["DEFAULT_SESSION_HEADERS_WIN_PRIV"].copy()


	def set_auth_header(self, header:dict, host: Union[str, None]=None) -> bool:
		# check header type
		if not isinstance(header, dict):
			self.__class__._log.error(f"set_auth_header TypeError header: {type(header)}")

			return False

		if host is None:
			self.SessH.headers.update(header)
			self.SessR.headers.update(header)
			self.__class__._log.info(f"set_auth_header general header with key {list(header.keys())} for Sessions {(self.SessH._SID, self.SessR._SID)}")
			
			return True

		else:
			self.auth_headers.update({host: header})
			
			# log it
			if not host in self.auth_headers:
				self.__class__._log.info(f"set_auth_header for host '{host}' with key {list(header.keys())} for runtime Session")
			else:
				self.__class__._log.info(f"set_auth_header updated host '{host}' with key {list(header.keys())} for runtime Session")

			return True


	def set_ratelimiter(self, per_sec:int) -> bool:
		self.Ratelimiter = RateLimiter(per_sec)


	def apply_auth(self, url:str, headers: Union[dict, None]) -> dict:
		# skip endpoints where it is not needed
		if url == "https://api.spacetraders.io/v2":
			return headers

		# use the account token for registering new agents
		if url == "https://api.spacetraders.io/v2/register" and url in self.auth_headers:
			if headers is None:
				headers = self.auth_headers[url]
			else:
				headers.update(self.auth_headers[url])

		# add general host token
		else:
			for host in self.auth_headers:
				if host in url and ("spacetraders.io" in url and (url not in ("https://api.spacetraders.io/v2/register", "https://api.spacetraders.io/v2/systems"))):
					# populate headers
					if headers is None:
						headers = self.auth_headers[host]
					else:
						headers.update(self.auth_headers[host])

					break

		return headers


	def __del__(self) -> None:
		# TODO detect if need close() and only call then

		if hasattr(self, "SessR"):
			self.SessR.close()
			self.__class__._log.warning(f"requests Session with _SID '{self.SessR._SID}' closed")

		if hasattr(self, "SessH"):
			self.SessH.close()
			self.__class__._log.warning(f"httpx Session with _SID '{self.SessH._SID}' closed")
