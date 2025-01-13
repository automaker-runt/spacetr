# Response


from hkeep.logger import get_logger
from utils.os_type import OS

# import sqlhandle for connect
# Settings need to be implemented
# Settings version needs to be implemented maybe through in the formatter extra=d

class Response(Inherit):

	log = get_logger(__name__)

	sql_table = None
	session = requests.Session()
	session._session_id = f"{OS[0]}{Settings.VERSION}_req1_{int(time.time())}"
	cl_session = httpx.Client()
	cl_session._session_id = f"{OS[0]}{Settings.VERSION}_hpx1_{int(time.time())}"

	if OS == "Linux":
		session.headers = Settings.DEFAULT_SESSION_HEADERS_LINUX.copy()
		cl_session.headers = session.headers.copy()
	else:
		session.headers = Settings.DEFAULT_SESSION_HEADERS_WIN.copy()
		cl_session.headers = session.headers.copy()
	

	@classmethod
	def get(cls, url:str, _printer:bool=False, btfsoup:bool=False, session:bool=False, timeout=(7, 3), protocol:str="req") -> requests.Response:
		start = int(time.time()*1000)
		# filter for valid protocol
		if not protocol.lower() in {"req", "hpx"}:
			raise Exception(f"Error Response.get parameter protocol is not supported: '{protocol}'")

		if session:
			if protocol == "req":	
				response = cls(Request.req("get", url, protocol=protocol, _printer=_printer, session=cls.session, timeout=timeout), _printer=_printer, btfsoup=btfsoup)			
			elif protocol == "hpx":
				response = cls(Request.req("get", url, protocol=protocol, _printer=_printer, session=cls.cl_session, timeout=timeout), _printer=_printer, btfsoup=btfsoup)			

		else:
			response = cls(Request.req("get", url, protocol=protocol, _printer=_printer, timeout=timeout), _printer=_printer, btfsoup=btfsoup)
			#response = Response(Request.req("get", url, _printer=_printer, session=False), _printer=_printer, btfsoup=btfsoup)

		if hasattr(response.response, "_past_resp") and len(response.response._past_resp) > 0:
			if _printer:	
				cls.log.info(f"Response acquired with {len(response.response._past_resp)+1} attempts and took {int(response.response._total_ti_ms/1000)}s")

			print(f"{int(time.time()*1000)} Response acquired with {len(response.response._past_resp)+1} attempts in total {int(response.response._total_ti_ms/1000)}s\n{list(str(i.text)[:200 if len(str(i.text)) > 1000 else len(str(i.text))] for i in response.response._past_resp)}", file=sys.stderr)

		return response

	
	@classmethod
	def reset_sess(cls) -> None:
		session = requests.Session()
		session_number = int(cls.session._session_id.split("_")[1][3:])
		session._session_id = f"{OS[0]}{Settings.VERSION}_req{session_number+1}_{int(time.time())}"
		
		if OS == "Linux":
			session.headers = Settings.DEFAULT_SESSION_HEADERS_LINUX.copy()
		else:
			session.headers = Settings.DEFAULT_SESSION_HEADERS_WIN.copy()
		
		cls.session.close()
		cls.session = session


	def reset_cl_sess(cls) -> None:
		cl_session = httpx.Client()
		cl_session_number = int(cls.cl_session._session_id.split("_")[1][3:])
		cl_session._session_id = f"{OS[0]}{Settings.VERSION}_hpx{cl_session_number+1}_{int(time.time())}"
		
		if OS == "Linux":
			cl_session.headers = Settings.DEFAULT_SESSION_HEADERS_LINUX.copy()
		else:
			cl_session.headers = Settings.DEFAULT_SESSION_HEADERS_WIN.copy()
		
		cls.cl_session.close()
		cls.cl_session = cl_session


	def __init__(self, response:requests.Response, _printer:bool=False, btfsoup:bool=False):
		self._printer = _printer	# self._printer is the attribute and self.printer is the method
		self.response = response
		#print(type(response), response.status_code, len(response.text))

		try:
			json.loads(self.response.text)
		except Exception as E:
			# error occured
			self.jj = dict()

			if btfsoup:
				if self.check_satus_code():
					if _printer:	
						print(f"response processed, beautifullsoup indicated, .response.text set")

				else:
					self.check_error()
			
			else:
				self.error = True
				print(f"{int(time.time()*1000)} {E} during json serialization, status code is ({self.response.status_code}) response.text: ({self.response.text if len(self.response.text) < 400 else 'len above 400'}), url ({self.response.url})", file=sys.stderr)
			
		else:	
			self.jj = response.json()

			if self.check_satus_code():
				if self._printer:	
					self.printer()
			else:
				self.check_error()

		finally:
			self.response.close()
			self.gen_jj()


	def gen_jj(self):
		pass


	def check_error(self) -> None:
		if self.error and not self._printer:
			if getattr(self, "error_message", False) and getattr(self, "error_reason", False):
				if self.error_reason != "Bogon IP error":	
					print(f"{int(time.time()+1000)} {self.error_reason}, message: {self.error_message}, url ({self.response.url})", file=sys.stderr)
			else:	
				print(f"{int(time.time())} Response is marked with error, probably during request", file=sys.stderr)


	def check_satus_code(self) -> bool:
		if self.response.status_code != 200:
			
			if "error" in self.jj and "title" in self.jj["error"] and "message" in self.jj["error"]:

				self.error_reason = self.jj["error"]["title"]
				self.error_message = self.jj["error"]["message"]
				
				if self._printer:	
					print(f"Request failed with code {self.response.status_code}:")
					print("\t", self.error_reason)
					print("\t", self.error_message)


			else:
				if self._printer:
					self.printer(mode="Error")

				self.error_reason = f"Unkown error"
				self.error_message = f"status code {self.response.status_code}"
			
			self.error = True

			return False

		else:
			self.error = False

			return True


	def procedure_write_sql(self, DB_fpath:str, max_tries=3, ignore_err:bool=False, excld_col:Union[list, tuple, set]=tuple()) -> bool:
		tries = 0
		# either ignore error and just exec_sql_INS()
		# or dont ignore error and self.error needs to be False to execute exec_sql_INS()
		if ignore_err or (not ignore_err and not self.error):
			
			while not self.exec_sql_INS(DB_fpath=DB_fpath, excld_col=excld_col):
				time.sleep(5)
				tries += 1
				# default: if after 3 attempts it didn't work, quit
				if tries >= max_tries:
					break

			if tries >= max_tries:
				return False

			else:
				return True

		else:
			return False


	def sql_INS(self, table=None, appl_jj=None) -> str:
		if table is None:
			table = self.__class__.sql_table

		# set appl_jj if None
		if appl_jj is None:
			appl_jj = self.jj

		if not hasattr(self, "_sql_INS"):
			cols = str(tuple(appl_jj.keys())).replace("'", "")

			re = f'''INSERT INTO {table} {cols} VALUES ({fill_sql_question_m(appl_jj)})'''

			self._sql_INS = re

		return self._sql_INS


	def exec_sql_INS(self, DB_fpath:str, table=None, excld_col:Union[list, tuple, set]=tuple()) -> bool:
		if table is None:
			table = self.__class__.sql_table
		
		# filter columns if any in excld_col
		appl_jj = self.jj.copy()
		if len(excld_col) > 0:	
			for col in excld_col:
				if col in appl_jj.keys():	
					appl_jj.pop(col)


		conn = sh.connect(DB_fpath)
		if conn is None:
			return False

		with conn:
			try:	
				conn.execute(self.sql_INS(table, appl_jj=appl_jj), tuple(appl_jj.values()))
				conn.commit()

			except Exception as sqlE:
				self.__class__.log(f'Error {sqlE} trying to save API changelog query', int(time.time()*1000))
				print(int(time.time()*1000), f"Error trying to execute ({self._sql_INS}) in ({DB_fpath}): {sqlE}", file=sys.stderr)

				return False
			
			else:
				return True


	def printer(self, mode="Standard"):
		print(f"{mode} Response printer")
		print(json.dumps(self.jj, indent=4))
