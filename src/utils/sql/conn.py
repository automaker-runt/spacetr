# conn
# Connections for DB-files in SQLite
import sqlite3
import time
from threading import get_ident
from typing import Union

from hkeep.log.logger import get_logger
from hkeep.error import tb
from utils.strings.shorten import short


class Connection:

	_log = get_logger(__name__)


	def __init__(self, dbfp:str, read_only:bool=False,
					open_conn:bool=False, persist:bool=False,
					key_id:str=''):
		self.dbfp = dbfp
		self.open_status = False
		self.Conn = None
		self.persist = persist
		self.key_id = key_id
		self.read_only = read_only
		self.thread_id = None

		if open_conn:
			self.open_DB(read_only=read_only)


	def open_DB(self, read_only:bool=False, _id:str='', attempt:int=1, max_retry:int=3) -> Union[sqlite3.Connection, None]:
		if len(_id) > 0:
			self.key_id = _id
		else:
			_id = self.key_id

		dbfp = self.dbfp

		conn = None
		
		try:
			conn = sqlite3.connect(f"file:{dbfp}?mode=ro", uri=True) if read_only else sqlite3.connect(dbfp)
		
		except Exception as E:
			
			if (attempt <= max_retry and 
				not (i in str(E) for i in (	"disk I/O error", 
											"unable to open database file"))
				):
				self.__class__._log.warning(f"attempted open DB {short(dbfp)}, {tb(E)}")
				time.sleep(3)				
				conn = self.open_DB(read_only=read_only, _id=_id, attempt=attempt+1)
			
			else:
				self.__class__._log.error(f"failed open DB {dbfp}, {tb(E)}")

				return
		
		if conn is not None:
			# log main Connection
			if self.persist:
				self.__class__._log.info(f"opened Connection '{_id}' to DB {short(dbfp)}{' as read only' if read_only else ''}")

			else:
				self.__class__._log.debug(f"opened Connection '{_id}' to DB {short(dbfp)}{' as read only' if read_only else ''}")
			
			self.Conn = conn
			self.open_status = True
			self.thread_id = get_ident()

		return conn


	def close_DB(self, pragma:str='', attempt:int=0, max_retry:int=3, force:bool=False) -> bool:
		self.__class__._log.debug(f"called close Connection '{self.key_id}' DB {short(self.dbfp)}")
		
		conn = self.Conn

		try:
			if len(pragma) > 0:
				cur = conn.cursor()
				cur.execute(f'''PRAGMA {pragma}''')
				cur.fetchall()
			
			conn.commit()
			conn.close()


		except sqlite3.ProgrammingError as PE:
			if "SQLite objects created in a thread can only be used in that same thread." in str(PE):
				self.__class__._log.warning(f"close_DB failed closing Conn '{self.key_id}', {tb(PE)}")
			else:
				self.__class__._log.critical(f"close_DB failed closing Conn '{self.key_id}', {tb(PE)}")

				raise PE

		except Exception as E:
			if force:
				conn.interrupt()

			if "database is locked" in str(E):
				if attempt < max_retry:
					self.__class__._log.warning(f"attempted close Connection '{self.key_id}' to DB {short(self.dbfp)}, {tb(E)}")
					time.sleep(3)

					return self.close_DB(conn, pragma, attempt=attempt+1)

				else:
					self.__class__._log.error(f"failed close Connection '{self.key_id}' to DB {self.dbfp}, {tb(E)}")

					return False

			else:
				self.__class__._log.error(f"failed close Connection '{self.key_id}' to DB {self.dbfp}, {tb(E)}")
				
				return False

		else:
			# log main Connection
			if self.persist:
				self.__class__._log.info(f"closed Connection '{self.key_id}' to DB {short(self.dbfp)}")

			else:
				self.__class__._log.debug(f"closed Connection '{self.key_id}' to DB {short(self.dbfp)}")

			self.open_status = False
			self.thread_id = None
			self.Conn = None

			return True
