# Request

import requests, httpx, time
import random as rnd

from typing import Union
from hkeep.logger import get_logger
from utils.os_type import OS


class Request:

	log = get_logger(__name__)


	@classmethod
	def req(cls, type:str,
				url:str,
				protocol:str="req",		# either "req" or "hpx"
				_printer:bool=False,
				session: Union[requests.Session, httpx.Client, bool]=False,
				count_max:int=15,
				past_reqs=None,
				timer_start=None,
				timeout:Union[int, tuple]=(7, 3)) -> requests.Response:
		
		if timer_start is None:
			timer_start = int(time.time()*1000)

		if past_reqs is None:
			past_reqs = list()

		def _query(getter, header={}, count=1, count_max=15, timeout=timeout):
			# try to get a valid response until count_max is reached
			try:
				resp = getter(url, headers=header, timeout=timeout)
				while resp.status_code != 200 and count < count_max:
					past_reqs.append(resp)
					time.sleep(rnd.randrange(90, 167, 1)/1000)
					count += 1
					resp = getter(url, headers=header)

					if resp.status_code >= 500 and resp.status_code < 600:
						count_max = 4
						time.sleep(1.5)

					# switch to httpx if we have a forbidden
					# try http/2 with httpx
					elif resp.status_code >= 400 and resp.status_code < 500:
						if isinstance(resp, requests.models.Response):
							getter = httpx.get
							time.sleep(0.84)
						else:
							break

			except (requests.ConnectionError, httpx.RequestError) as Err:
				return _query(getter, header=header, count=count, count_max=count_max-count)

			except (requests.Timeout, httpx.TimeoutException) as TErr:
				t1, t2 = timeout
				timeout = tuple([t1+5, t2+5])

				return _query(getter, header=header, count=count, count_max=count_max-count, timeout=timeout)

			except Exception as E:
				if any(i in str(E) for i in ("Connection reset by peer", 
												"Broken pipe")):
					return _query(getter, header=header, count=count, count_max=count_max-count)
				else:
					cls.log.error(f"Error in Request with session({session}), count({count}), timer({int(time.time()*1000)-timer_start}ms), line({E.__traceback__.tb_lineno}): {E}")
					if not isinstance(session, bool):	
						if protocol == "req":	
							Response.reset_sess()
						elif protocol == "hpx":	
							Response.reset_cl_sess()
					traceback.print_tb(E.__traceback__, limit=5)

			else:
				resp._past_resp = past_reqs
				resp._total_ti_ms = int(time.time()*1000)-timer_start
				resp.time = timer_start

				return resp

		# filter for HTTP method
		if type.lower() != "get":
			raise Exception(f"Error Request.req parameter type is not supported: '{type}'")

		# filter for valid protocol
		if not protocol.lower() in {"req", "hpx"}:
			raise Exception(f"Error Request.req parameter protocol is not supported: '{protocol}'")

		# use provided session
		if isinstance(session, requests.Session) or isinstance(session, httpx.Client):

			if OS == "Linux":
				headers_host = {}

			else:	
				# set host key for non Linux headers
				if url.find(":") != -1:		
					if url[url.find(":")+3:].find("/") != -1:
						_host = url[url.find(":")+3:url[url.find(":")+3:].find("/")+url.find(":")+3]	# "https://developers.binance.com/docs/derivatives/change-log" -> "developers.binance.com"
					else:
						_host = url[url.find(":")+3:]	# "https://developers.binance.com"
				else:
					_host = 'cloudfront.net'
				headers_host = {'Host': _host}

			re = _query(session.get, headers_host)

			if hasattr(session, "_session_id"):
				if protocol == "req":
					# set session id according to which protocol was used
					# session is Response.session, but in case status_code is 4xx
					# query uses httpx.get as last resort, we can't set session._session_id
					# to a httpx.get request
					re._session_id = session._session_id if isinstance(re, requests.Response) else None
				elif protocol == "hpx":
					re._session_id = session._session_id

		# use one time request
		else:
			if protocol == "req":	
				re = _query(requests.get, header={'Connection': 'close', 'Accept-Encoding': None, 'Accept': '*/*'})
			elif protocol == "hpx":
				re = _query(httpx.get, header={'Connection': 'close', 'Accept-Encoding': None, 'Accept': '*/*'})
		
		# in case the attempt was not successful, reset the session
		if re.status_code != 200 and not isinstance(session, bool) and hasattr(session, "_session_id"):
			if "req" in session._session_id:
				Response.reset_sess()
			elif "hpx" in session._session_id:
				Response.reset_cl_sess()

		return re
