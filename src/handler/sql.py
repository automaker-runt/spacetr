# sql handler
import sqlite3
import time
from typing import Union

from hkeep.error import tb
from hkeep.logger import get_logger
from utils.sql.schemer import Scheme
from utils.strings.shorten import short


class SqlHand:

	_log = get_logger(__name__)


	def __init__(self, scheme:Scheme, dbfp:str) -> None:
		self.scheme = scheme
		# decide whether to have always an open DB connection
		# or open and close it, or choosing which from both to do
		# on instance basis

		# create the template for the SQL join statements
		'''
		SELECT 
			log.id, time_UTC, _loglvl.name, _logger.name, content
		FROM log
		INNER JOIN _logger ON log.logger_id = _logger.id
		INNER JOIN _msg ON log.msg_id = _msg.id
		INNER JOIN _loglvl ON log.loglvl_id = _loglvl.id;
		'''

		# determine all SELECT templates from self.scheme.dependancies


	def open_db(self, dbfp:str, read_only:bool=False, attempt:int=0, max_retry:int=3) -> Union[sqlite3.Connection, None]:
		conn = None
		
		try:
			conn = sqlite3.connect(f"file:{dbfp}?mode=ro", uri=True) if read_only else sqlite3.connect(dbfp)
		
		except Exception as E:
			if attempt < max_retry:
				self.__class__._log.warning(f"attempted open DB {short(dbfp)}, {tb(E)}")
				time.sleep(3)
				conn = self.open_db(dbfp, read_only=read_only, attempt=attempt+1)
			else:
				self.__class__._log.error(f"failed open DB {dbfp}, {tb(E)}")
		
		if conn is not None:
			conn._dbfp = dbfp
			self.__class__._log.info(f"opened DB {short(dbfp)}")

		return conn


	def close_db(self, conn:sqlite3.Connection, pragma:str='', attempt:int=0, max_retry:int=3, force:bool=False) -> bool:
		try:
			if len(pragma) > 0:
				cur = conn.cursor()
				cur.execute(f'''PRAGMA {pragma}''')
				cur.fetchall()
			
			conn.commit()
			conn.close()


		except Exception as E:
			if force:
				conn.interrupt()

			if "database is locked" in str(E):
				if attempt < max_retry:
					self.__class__._log.warning(f"attempted close DB {short(conn._dbfp)}, {tb(E)}")
					time.sleep(3)

					return self.close_db(conn, pragma, attempt=attempt+1)

				else:
					self.__class__._log.error(f"failed close DB {conn._dbfp}, {tb(E)}")

					return False

			else:
				self.__class__._log.error(f"failed close DB {conn._dbfp}, {tb(E)}")
				
				return False

		else:
			self.__class__._log.info(f"closed DB {short(conn._dbfp)}")

			return True
