# sql handler
import sqlite3
import time
from typing import Union

from hkeep.error import tb
from hkeep.log.logger import get_logger
from hkeep.log.misc import adjust_sql_sel_outp_loglvl, adjust_sql_sel_outp_col_order
from utils.sql.scheme import Scheme
from utils.strings.format import Formatter
from utils.strings.shorten import short


class SqlHand:

	_log = get_logger(__name__)


	def __init__(self, scheme:Scheme, dbfp:str, formatter: Union[Formatter, None]=None) -> None:
		self.scheme = scheme
		self.dbfp = dbfp
		self.formatter = formatter
		# decide whether to have always an open DB connection
		# or open and close it, or choosing which from both to do
		# on instance basis

		# determine all SELECT templates from self.scheme.dependancies
		# add formatter
		# add support for CREATE TABLE
		# add support for INSERT

		self.open_db(dbfp)


	def sel(self, com:str) -> list:
		com = com.strip()
		
		l_com = com.split()
		# find table name by looking for the next item after "FROM"
		table = l_com[l_com.index("FROM")+1].strip(';,')
		# find selected columns by looking for the next item after "SELECT"
		# until index of "FROM"
		columns = l_com[1:l_com.index("FROM")]
		columns = [i.strip(',') for i in columns]
		dependancies = list()

		# checking if table from select is a table in schemes
		# and has foreign keys
		if table in self.scheme.schemes:
			# look whether select mentions columns with dependancy
			for col in columns:
				# now we build from columns mentioned in select their
				# <table>.<column> equivalent applying naming convention
				if f"{table}.{col}_id" in self.scheme.dependancies:
					dependancies.append(f"{table}.{col}_id")

		# now we know the SELECT is affected by items in dependancies
		# start with com_str until FROM <table>
		com_str = ' '.join(l_com[:l_com.index("FROM")+1])+' '+table
		for key in dependancies:
			value = self.scheme.dependancies[key]
			left_join_block = f'\nLEFT JOIN {value[:value.find(".")]} ON {key} = {value}'
			com_str += left_join_block

		# now finish com_str by adding any WHERE/LIMIT/ORDER BY statements
		com_str += '\n'+' '.join(l_com[l_com.index("FROM")+2:])
		
		# assure sql statement is ending with ";"
		if any([com_str[-2:] == "\n", com_str[-1] != ";"]):
			com_str = com_str.strip()+';'
		elif com_str[-1] == ";":
			pass
		else:
			self.__class__._log.warning(f"com_str is ending in undefined characters: {short(com_str)}")

		# apply formatter if available
		if self.formatter is None:
			
			return self._exec_com(com_str)
		
		elif isinstance(self.formatter, Formatter):
			
			return self.apply_formatter(
										sql_outp=self._exec_com(com_str),
										sql_outp_col_order=columns
										)


	def _exec_com(self, com:str) -> Union[None, list]:
		cur = self.conn.cursor()
		cur.execute(com)
		re = cur.fetchall()
		cur.close()

		return re


	def use_formatter(self, formatter:Formatter) -> bool:
		self.formatter = formatter

		return True


	def apply_formatter(self, 	sql_outp:list, 
								sql_outp_col_order:list, 
								safe=True) -> list:

		# correlates the order of the select columns with the sql-output order
		# and applies the string template self.formatter to transform sql-output
		# into list of strings of sql results that are formated through template

		# keep track of the results columns' order and their corresponding indexes
		# in this dict
		
		# make sure sql_outp_col_order doesn't have references to tables
		# <table>.<column> doesn't work with Templates, '.' is not working
		sql_outp_col_order = adjust_sql_sel_outp_col_order(sql_outp_col_order)

		identifier_order = dict() 
		
		for identifier in self.formatter.templ.get_identifiers():
			if identifier in sql_outp_col_order:
				identifier_order.update({identifier: sql_outp_col_order.index(identifier)})

		# now we can replace the sql_outp by mapping with identifier_order
		lines = list()

		for line in sql_outp:
			
			# misc intervention so we can replace loglvl with a lfjust loglvl
			if "loglvl" in identifier_order:
				line = adjust_sql_sel_outp_loglvl(line, identifier_order)

			mapper = {ident: line[identifier_order[ident]] for ident in identifier_order}

			if safe:
				lines.append(self.formatter.apply_safe(mapper))
			else:
				s = self.formatter.apply(mapper)
				if s is not None:	
					lines.append(s)

		return lines


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
			self.__class__._log.info(f"opened DB {short(dbfp)}")
			self.conn = conn
			self.dbfp = dbfp

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
					self.__class__._log.warning(f"attempted close DB {short(self.dbfp)}, {tb(E)}")
					time.sleep(3)

					return self.close_db(conn, pragma, attempt=attempt+1)

				else:
					self.__class__._log.error(f"failed close DB {self.dbfp}, {tb(E)}")

					return False

			else:
				self.__class__._log.error(f"failed close DB {self.dbfp}, {tb(E)}")
				
				return False

		else:
			self.__class__._log.info(f"closed DB {short(self.dbfp)}")

			return True


	def __del__(self):
		self.__class__._log.debug(f"deleting SqlHand obj and closing DB {short(self.dbfp)}")

		if not self.close_db(self.conn):
			self.close_db(self.conn, force=True)
