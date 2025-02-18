# request

import datetime, time, traceback, io, json, queue, os
import requests, httpx
from typing import Union

from fsys.folderinit.folder import Folder
from handler.sql import SqlHand
from hkeep.error import tb
from hkeep.log import logger
from utils.blank_obj import Blank
from utils.dicts import multidicts, lose
from utils.os_type import OS
from utils.sql.scheme import Schemers
from utils.strings.xxhash import getHash64
from utils.time import conv_time_time_to_def


class Request:
	# logs loglvl NETMSG
	# inserts into own DB



		# TODO
		# need to define netmsg logging.Formatter with all info needed
		# then need to find out how to pass all extra args into self.__class__.netmsg()

	_log = logger.get_logger(__name__)
	netmsg = False
	netSH = None
	netmsg_Q = None

	priv_headers = {"DEFAULT_HEADERS_LINUX_PRIV": {
															'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
															'Accept-Encoding': 'gzip, deflate, br, zstd',
															'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
															'Priority': 'u=0, i',
															'Connection': 'close',
															'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126"',
															'Sec-Ch-Ua-Platform': 'Linux',
															'Sec-Fetch-Dest': 'document',
															'Sec-Fetch-Mode': 'navigate',
															'Sec-Fetch-Site': 'same-origin',
															'Upgrade-Insecure-Requests': '1',
															'User-Agent': 'Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
															},
					"DEFAULT_HEADERS_WIN_PRIV": {
															'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
															'Accept-Encoding': 'gzip, deflate, br',
															'Accept-Language': 'en-US,en;q=0.5',
															'Connection': 'close',
															'Sec-Fetch-Dest': 'document',
															'Sec-Fetch-Mode': 'navigate',
															'Sec-Fetch-Site': 'same-origin',
															'Upgrade-Insecure-Requests': '1',
															'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
															}
															}


	@classmethod
	def set_netmsg(cls, Q:queue.Queue, dbfp:str, scfp:str) -> SqlHand:
		#cls.netmsg = logging.getLogger("netmsg")
		cls.netmsg_Q = Q
		netSchemer = Schemers(importerfp=scfp)

		dbf = os.path.abspath(dbfp)

		cls.netSH = SqlHand(netSchemer, dbf)

		cls.netmsg = True

		return cls.netSH
	

	@classmethod
	def unset_netmsg(cls) -> None:
		cls.netmsg = False

		time.sleep(0.2)
		cls.netSH.close()
		time.sleep(0.2)

		cls.netSH = None
		cls.netmsg_Q = None


	def __init__(self, getter,
						url:str,
						data:dict=dict(),
						headers:dict=dict(),
						jjs:dict=dict(),
						timeout:tuple=(5,5),
						private:bool=False,
						cookies: Union[dict, requests.cookies.RequestsCookieJar]=dict()
			):
		# jjs is a dict with all important attributes of parent Obj "Response"

		self.getter = getter
		self.url = url
		self.data = data
		self.jjs = jjs
		
		# headers according to private and OS
		self.headers = headers
		# set default headers for private if no session
		if self.jjs["SID"] == 0 and (private or self.jjs["private"]):
			if OS == "Linux":
				self.headers.update(self.__class__.priv_headers["DEFAULT_HEADERS_LINUX_PRIV"])
			else:
				self.headers.update(self.__class__.priv_headers["DEFAULT_HEADERS_WIN_PRIV"])

		self.timeout = timeout
		self.error = 0
		self.private = private
		self.cookies = cookies
		self._reqID = None		


	def run(self, count:int=1, max_count:int=6) -> Union[httpx.Response, requests.models.Response]:

		# abort if count == max_count
		if count == max_count:
			Resp = list()
			setattr(Resp, "Error", 1)

			return Resp

		self._reqID = getHash64(self._form_atrib_dict())
		start_ti = time.time()

		try:			
			# for mode=get
			if self.jjs["mode"] == "get":
				#Resp = self.getter(self.url, headers=self.headers, timeout=self.timeout)
				Resp = self.getter.get(self.url, headers=self.headers, cookies=self.cookies, timeout=self.timeout)

			# for mode=post
			elif self.jjs["mode"].split()[0] == "post":
				jjs = self.jjs["mode"].split()
				
				if len(jjs) > 1 and jjs[1] == "data":
					Resp = self.getter.post(self.url, headers=self.headers, cookies=self.cookies, data=self.data, timeout=self.timeout)

				elif len(jjs) > 1 and jjs[1] == "json":
					Resp = self.getter.post(self.url, headers=self.headers, cookies=self.cookies, json=self.data, timeout=self.timeout)


		except (requests.ConnectionError, httpx.RequestError) as Err:
			end_ti = time.time()
			Resp = Blank()
			self.error = str(Err)
			self.register_Resp(Resp, start_ti, end_ti, count, error=True)
			self.__class__._log.warning(f"run encountered {str(Err)}")
			setattr(Resp, "ReqTimeout", 1)
			setattr(Resp, "_reqID", self._reqID)
			# adjust timeout only on specific timeout error
			if "The read operation timed out" in str(Err):
				t1, t2 = self.timeout
				self.timeout = tuple([t1+4, t2+4])
			
			if "Request URL is missing an" in str(Err):
				setattr(Resp, "Error", 1)
				del Resp.ReqTimeout
				return Resp

			return self.run(count+1) if count+1 <=max_count else Resp

		except (requests.Timeout, httpx.TimeoutException) as TErr:
			end_ti = time.time()
			Resp = Blank()
			self.error = str(TErr)
			self.register_Resp(Resp, start_ti, end_ti, count, error=True)
			self.__class__._log.warning(f"run encountered {str(TErr)}")
			setattr(Resp, "ReqTimeout", 1)
			setattr(Resp, "_reqID", self._reqID)
			t1, t2 = self.timeout
			self.timeout = tuple([t1+4, t2+4])

			return self.run(count+1) if count+1 <=max_count else Resp

		except Exception as E:

			end_ti = time.time()
			Resp = Blank()
			setattr(Resp, "Error", 1)
			setattr(Resp, "_reqID", self._reqID)
			self.error = str(E)
			self.register_Resp(Resp, start_ti, end_ti, count, error=True)
			

			# some other Exception handling
			if any(i in str(E) for i in ("Connection reset by peer", 
										"Broken pipe")):
				
				self.__class__._log.warning(f"run encountered {str(E)}")

				return self.run(count+1) if count+1 <=max_count else Resp

			else:
				temp = io.StringIO()
				traceback.print_tb(E.__traceback__, limit=25, file=temp)
				temp.seek(0)
				self.__class__._log.critical(f"run failed with unknown Exception, {tb(E)}\n{temp.getvalue()}")
				temp.close()

				return Resp

		else:
			end_ti = time.time()
			self.error = 0
			setattr(Resp, "_reqID", self._reqID)
			self.register_Resp(Resp, start_ti, end_ti, count)

			return Resp


	def register_Resp(self, 	Resp: Union[httpx.Response, requests.models.Response],
								start:float,
								end:float,
								count:int,
								error:bool=False) -> bool:
		
		if not error:	
				
			# check if headers has date key
			if "date" in Resp.headers:
				resp_headers_date = Resp.headers.pop("date")
				if isinstance(resp_headers_date, tuple):
					resp_headers_date, *d = resp_headers_date
				Resp.headers.update({"date": ""})

			else:
				resp_headers_date = 0

			# check if resp_body is json-able
			resp_body = Resp.content.decode() if self.jjs["lib"] == "hpx" else Resp.text
			try:
				js_resp_body = json.loads(resp_body)

			except (json.JSONDecodeError, UnicodeDecodeError) as err:
				# body is not a json
				resp_body_traceID = 0

			else:
				# check in resp_body for key that has forms of "Trace-Id"
				resp_body, resp_body_traceID = lose.keys(js_resp_body, ("Trace-Id", "traceid", "trace-context"))

			# set response headers as dict
			if self.jjs["lib"] == "hpx":
				resp_headers = multidicts.make_dict(Resp.headers)
			else:
				resp_headers = dict(Resp.headers)

			# check in resp_headers for key that has forms of "Trace-Id" / "trace-context"
			resp_headers, re_trace = lose.keys(resp_headers, ("Trace-Id", "traceid", "trace-context", "Etag"))

			# if spacetraders.io
			if "spacetraders.io" in self.url:	
				# also lose the ratelimit reset time for the DB, keep it in Resp.headers for Response to use it
				resp_headers, _ = lose.keys(json.loads(resp_headers), ("x-ratelimit-reset",))

			# if trace in headers found, set/add to resp_body_traceID
			if re_trace != 0:
				if resp_body_traceID == 0:
					resp_traceID = re_trace
				else:
					resp_traceID = [re_trace, resp_body_traceID]
			# no trace in headers, set to whatever body had
			else:
				resp_traceID = resp_body_traceID

			self.columns ={
					"time_UTC": conv_time_time_to_def(start),
					"reqID": self._reqID,
					"respID": self.jjs["respID"],
					"SID": self.jjs["SID"],
					"attempt": self.jjs["attempts"],
					"count": count,
					"url": self.url,
					"mode": self.jjs["mode"].upper(),
					"private": self.jjs["private"],
					"req_headers": multidicts.make_dict(Resp.request.headers) if self.jjs["lib"] == "hpx" else Resp.request.headers,
					"req_body": Resp.request.content.decode() if self.jjs["lib"] == "hpx" else str(Resp.request.body),
					"status_code": Resp.status_code,
					"resp_reason": Resp.reason_phrase if self.jjs["lib"] == "hpx" else Resp.reason,
					"resp_headers": resp_headers,
					"resp_body": resp_body,
					"resp_traceID": resp_traceID,
					"invalid_reason": str(self.jjs["invalid_reason"]),
					"resp_protocol": Resp.http_version if self.jjs["lib"] == "hpx" else f"HTTP/{Resp.raw.version/10}",
					"lib": self.jjs["lib"],
					"timeout": self.timeout,
					"resp_headers_date": resp_headers_date,
					"resp_elapsed": Resp.elapsed,
					"own_elapsed": datetime.timedelta(seconds=end-start),
					"resp_cookies": dict(Resp.cookies) if self.jjs["lib"] == "hpx" else Resp.cookies.get_dict(),
					"error": self.error
			}

		else:
			self.columns ={
					"time_UTC": conv_time_time_to_def(start),
					"reqID": self._reqID,
					"respID": self.jjs["respID"],
					"SID": self.jjs["SID"],
					"attempt": self.jjs["attempts"],
					"count": count,
					"url": self.url,
					"mode": self.jjs["mode"].upper(),
					"private": self.jjs["private"],
					"req_headers": 0,
					"req_body": str(self.data),
					"status_code": 0,
					"resp_reason": 0,
					"resp_headers": 0,
					"resp_body": 0,
					"resp_traceID": 0,
					"invalid_reason": str(self.jjs["invalid_reason"]),
					"resp_protocol": 0,
					"lib": self.jjs["lib"],
					"timeout": self.timeout,
					"resp_headers_date": 0,
					"resp_elapsed": 0,
					"own_elapsed": datetime.timedelta(seconds=end-start),
					"resp_cookies": 0,
					"error": self.error
			}

		if self.__class__.netmsg:

			self.__class__.netmsg_Q.put(list(self.columns.values()))			

		else:
			g = [print(k, ' :\t\t\t', v) for k, v in self.columns.items()]

			print('\n\n\n')


	def _form_atrib_dict(self) -> dict:
		re_dict = {
					"url": self.url,
					"data": self.data,
					"headers": self.headers,
					"jjs": self.jjs,
					"timeout": self.timeout,
					"error": self.error,
					"private": self.private,
					"_reqID": self._reqID
					}

		return re_dict
