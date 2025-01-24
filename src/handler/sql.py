# sql handler
import sqlite3
import time
from typing import Union

from hkeep.error import tb
from hkeep.log.logger import get_logger
from hkeep.log.misc import adjust_sql_sel_outp_loglvl, adjust_sql_sel_outp_col_order
from utils.sql.scheme import Scheme
from utils.sql import strings
from utils.strings.format import Formatter, DeFormatter
from utils.strings.shorten import short, shortb


class SqlHand:

	_log = get_logger(__name__)


	def __init__(	self, scheme:Scheme,
					dbfp:str,
					deformatter: Union[dict, None]=None,
					formatter: Union[tuple, None]=None) -> None:
		# check for scheme successfull finalization
		if not scheme.finalized and not scheme.finalize():
			self.scheme = Scheme(tables=scheme.tables)
			self.__class__._log.warning(f"initialized SqlHand without finalized Scheme obj; self.scheme.add_schema & self.scheme.finalize & run self.init_scheme needed")
		else:
			self.scheme = scheme
		
		self.dbfp = dbfp

		# check for valid formatter types and set self.formatter
		# formatter argument needs to be either 2 level tuples ((table, Formatter), (table, Formatter))
		# or a simple tuple (table, Formatter) with table being a str
		# and Formatter being the class Formatter
		self.formatter = dict()
		if formatter is None:
			pass
		elif isinstance(formatter, tuple):
			if len(formatter) > 0 and isinstance(formatter[0], tuple):
				for form in formatter:
					self.formatter.update({form[0]: form[1]})

			elif len(formatter) > 0 and isinstance(formatter[0], str):
				self.formatter.update({formatter[0]: formatter[1]})

			else:
				self.__class__._log.warning(f"initialized SqlHand with wrong formatter type or invalid structure")
		else:
			self.__class__._log.warning(f"initialized SqlHand with wrong formatter type")
		
		# deformatter is supposed to also be table boound
		# needs to be given as dict, with key specifying table
		# and value the DeFormatter Obj
		if isinstance(deformatter, dict):
			self.deformatter = deformatter
		else:
			self.deformatter = dict()

		# TODO decide whether to have always an open DB connection
		# or open and close it, or choosing which from both to do
		# on instance basis		


	def ins(self, table:str, inp: Union[list, str]) -> bool:
		
		# TODO
		# decide whether to use constant for version

		multiple_ins = False
		# check inp for type and structure (multiple lines or just one?)
		if isinstance(inp, list):
			if len(inp) == 1:
				if isinstance(inp[0], str):
						# deformat the string to a list of strings for the
						# single line of inp
						if table in self.deformatter:
							inp = self.deformatter[table].apply(inp[0])

				else:
					self.__class__._log.error(f"ins inp single list item TypeError not being str: {type(inp[0])}")

					return False 
				
			elif len(inp) > 1:
				multiple_ins = True
				deform = table in self.deformatter
				# need to cycle through all 2nd lvl str
				_indx = 0
				for line in inp.copy():
					if deform:
						if not isinstance(line, str):
							self.__class__._log.error(f"ins inp list item '{line}' TypeError not being str: {type(line)}")

							return False

						inp[_indx] = self.deformatter[table].apply(line)
						_indx += 1
					
					else:
						if isinstance(line, str):
							self.__class__._log.error(f"ins inp list item '{line}' TypeError being str: {type(line)}")

							return False

			else:
				self.__class__._log.error(f"ins inp being an empty list: {inp}")

				return False

		elif isinstance(inp, str):	
			# deformat the string to a list of strings for the
			# single line of inp
			if table in self.deformatter:
				inp = self.deformatter[table].apply(inp)

		else:
			self.__class__._log.error(f"ins TypeError due to inp not being a list or str: {type(inp)}")

			return False

		column_order = self.scheme.schemes[table].columns

		if not multiple_ins:
			return self._ins_one(table, inp, column_order)

		else:
			result = True
			for i in inp:
				if not self._ins_one(table, i, column_order):
					result = False

			return result


	def _ins_one(self, table:str, one:list, col_order:list) -> bool:
		
		if "id" in col_order:	
			col_order.remove("id")

		# have to process every column of the table for INSERT
		for col in col_order:

			_tbl_cl_comb = f"{table}.{col}"
			# except PRIMARY KEY AUTOINCREMET
			if col.lower() == "id":
				continue
			
			# check for dependancies
			elif _tbl_cl_comb in self.scheme.dependancies:				

				# lookup col with it's specific col_order.index() as one[index]' value
				# in specific table
				# if value is in that table, grab the id and replace one[index]' value with id
				# if it is not in there, INS, grab then id and replace one[index]' value with id
				# do this for all dep_cols

				_indx = col_order.index(col)
				if isinstance(one, list) and len(one) > _indx:
					_val = one[_indx]
				else:
					self.__class__._log.error(f"_ins_one one is either not a list or len of it is smaller than _indx")
					self.__class__._log.info(f"_ins_one type(one):{type(one)} && len(one)({len(one)}), _indx({_indx}), one({one}), col_order({col_order})")

					return False

				ref_tbl_cl_comb = self.scheme.dependancies[_tbl_cl_comb]
				ref_tbl = ref_tbl_cl_comb[:ref_tbl_cl_comb.find('.')]
				ref_cl_id = ref_tbl_cl_comb[ref_tbl_cl_comb.find('.')+1:]
				ref_cl_val = f"{ref_tbl[1:]}"

				com = f"SELECT id FROM {ref_tbl} WHERE {ref_cl_val}=?;"
				com_var = (_val,)
				
				self.__class__._log.debug(f"_ins_one sel id from '{ref_tbl}' WHERE {ref_cl_val}={_val}")
				re = self.sel(com, com_var, _format=False)

				# check for results, to know if _val already in there
				if re is not None and len(re) > 0:
					_id = re[0][0]
					one[_indx] = _id
					self.__class__._log.debug(f"_ins_one sel id from '{ref_tbl}' WHERE {ref_cl_val}={_val} returned id={_id}")

				# if error occured re is None
				elif re is None:
					self.__class__._log.error(f"_ins_one value({_val}) lookup in '{ref_tbl}.{ref_cl_val}' returned None")
					self.__class__._log.info(f"_ins_one self.scheme.dependancies: {self.scheme.dependancies}")

					return False

				# expect len to be 0, aka not in there
				else:
					self.__class__._log.debug(f"_ins_one sel from '{ref_tbl}' WHERE {ref_cl_val}={_val} returned len 0")

					re_ins = self.ins(ref_tbl, [_val])
					self.__class__._log.debug(f"_ins_one insert into ref_tbl({ref_tbl}) {ref_cl_val}={_val} returned {re_ins}")

					if re_ins:
						self.__class__._log.debug(f"_ins_one insert into '{ref_tbl}' {ref_cl_val}={_val} successful")
						# now need to grab id
						re = self.sel(com, com_var, _format=False)

						# re should have len and be list now
						if re is None or len(re) == 0:
							self.__class__._log.error(f"_ins_one sel from '{ref_tbl}' WHERE {ref_cl_val}={_val} returned NoneType or len 0 after specific insert")

							return False

						# insert+select success
						else:
							_id = re[0][0]
							one[_indx] = _id
							self.__class__._log.debug(f"_ins_one after ins sel id from '{ref_tbl}' WHERE {ref_cl_val}={_val} returned id={_id}")
						
					else:
						self.__class__._log.error(f"_ins_one failed insert into '{ref_tbl}' {ref_cl_val}={_val}")

						return False

		# until here one has been redacted and values should have been replaced with the
		# ids of the foreign keys

		ins_dict = dict()
		for k, v in zip(col_order, one):
			ins_dict.update({k: v})

		where = str()
		for col in ins_dict.keys():
			where += f"{col}=? AND "

		# sel what we just want to insert, if it returns len > 0, we don't insert
		re_id = self.sel(f"SELECT id FROM {table} WHERE {where[:-5]};", tuple(ins_dict.values()), _format=False)
		if len(re_id) == 0:			

			cols = str(tuple(ins_dict.keys())).replace("'", "")
			if len(col_order) == 1:
				cols = cols.replace(',', '')
			com = f"INSERT INTO {table} {cols} VALUES ({strings.fill_sql_question_m(ins_dict)});"

			if not isinstance(self._exec_com(com, tuple(ins_dict.values())), list):
				self.__class__._log.error(f"_ins_one failed insert in {table} {[(i, j) for i,j in ins_dict.items()]}")

				return False

			else:
				self.__class__._log.debug(f"_ins_one inserted in {table} {[(i, j) for i,j in ins_dict.items()]}")

				return True

		else:
			# case for debug -> more details, info -> less details
			if self.__class__._log.isEnabledFor(10):	
				self.__class__._log.debug(f"_ins_one prevented duplicate insert into {table} of columns{tuple(ins_dict.keys())} and values{tuple(ins_dict.values())}, their id: {re_id}")
			else:
				self.__class__._log.warning(f"_ins_one prevented duplicate insert into {table}, value's id: {re_id}")

			return False


	def sel(self, com:str, com_var:tuple=tuple(), _format:bool=True) -> list:
		com = com.strip().replace('\n', '')
		
		l_com = com.split()
		# find table name by looking for the next item after "FROM"
		table = l_com[l_com.index("FROM")+1].strip(';,')
		# find selected columns by looking for the next item after "SELECT"
		# until index of "FROM"
		# can't look it up in self.scheme.schemes[table].columns, because not all may be selected
		columns = l_com[1:l_com.index("FROM")]
		columns = [i.strip(',') for i in columns]
		
		# checking if table from select is a table in schemes
		# and has foreign keys
		dependancies = self._grab_dependancies(table=table, columns=columns)
		self.__class__._log.debug(f"sel dependancies: {dependancies}")

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
		com_str = self._check_com_str_semic(com_str)
		self.__class__._log.debug(f"sel com_str: '{com_str}'")

		re = self._exec_com(com_str, com_var)

		# check validity of re
		if isinstance(re, list) and len(re) > 0:
			# apply formatter if available			
		
			# check if we want to format or not
			if _format:	
				# for when table is in self.formatter dict
				if isinstance(self.formatter, dict) and table in self.formatter:
				
					self.__class__._log.debug("sel applying formatter")
					return self.apply_formatter(table=table,
												sql_outp=re,
												sql_outp_col_order=columns)

				# for when self.formatter is None and in case self.formatter is dict but table not in it
				elif self.formatter is None or (isinstance(self.formatter, dict) and not table in self.formatter):
					self.__class__._log.debug("sel not applying formatter")

					return re

				else:
					self.__class__._log.error(f"sel failed to return due to self.formatter type({type(self.formatter)})")

					return list()

			# we set _format=False, we don't want apply_formatter even if available
			else:
				return re
		
		# re not valid
		else:
			return list()


	def _exec_com(self, com:str, com_var_tup:tuple=tuple()) -> Union[list, bool]:
		cur = self.conn.cursor()
		
		try:	
			# execute com with com_var_tup if needed
			if len(com_var_tup) > 0:
				cur.execute(com, com_var_tup)
			else:
				cur.execute(com)

		except Exception as E:
			self.__class__._log.error(f"failed sql command({com}, {com_var_tup}), {tb(E)}")

			return False

		else:
		
			re = cur.fetchall()

			if self.__class__._log.isEnabledFor(10):	
				com_var_tup_str = f", {com_var_tup}" if len(com_var_tup) > 0 else ""
				re_snippet = f" resulting in {len(re)} lines, 1st one: {shortb(re[0])}" if len(re) > 0 else ""
				self.__class__._log.debug(f"executed sql command '{com}'{com_var_tup_str}{re_snippet}")

			self.conn.commit()

			# make sure re is a list, even empty, but has to be list
			if not isinstance(re, list):
				return list()
			else:
				return re

		finally:
			cur.close()


	def _grab_dependancies(self, table:str, columns:list) -> list:
		dependancies = list()

		# checking if table from select is a table in schemes
		# and has foreign keys
		if table in self.scheme.schemes:
			# look whether select mentions columns with dependancy
			for col in columns:
				col = self.scheme.__class__._col_redact_from_table(col)
				# now we build from columns mentioned in select their
				# <table>.<column> equivalent applying naming convention
				if f"{table}.{col}_id" in self.scheme.dependancies:
					dependancies.append(f"{table}.{col}_id")

		return dependancies


	def _check_com_str_semic(self, com_str:str) -> str:
		# assure sql statement is ending with ";"
		if com_str[-2:] == "\n" or com_str[-1] != ";":
			com_str = com_str.strip()+';'
		elif com_str[-1] == ";":
			pass
		else:
			self.__class__._log.warning(f"com_str is ending in undefined characters: {short(com_str)}")

		return com_str


	def use_formatter(self, formatter:Formatter, table:str=str()) -> bool:
		table = table.strip().lower()

		if len(self.scheme.tables) == 1:
			saved = self.scheme.tables.copy().pop().strip().lower()
			if len(table) > 0 and table != saved:
				self.__class__._log.warning(f"gave use_formatter different table '{table}' than the single table in self.scheme.tables: '{saved}'")
				self.formatter[saved] = formatter
			else:	
				self.formatter[saved] = formatter

			table = saved

		elif len(self.scheme.tables) > 1 and len(table) > 0:
			self.formatter[table] = formatter

		elif len(self.scheme.tables) >= 0 and len(table) == 0:
			self.__class__._log.warning(f"didn't select specific table from self.scheme.tables in use_formatter to use Formatter with")

			return False
		
		self.__class__._log.info(f"set specific Formatter for table '{table}'")

		return True


	def apply_formatter(self, 	table:str,
								sql_outp:list, 
								sql_outp_col_order:list, 
								safe:bool=True) -> list:

		# correlates the order of the select columns with the sql-output order
		# and applies the string template self.formatter[table] to transform sql-output
		# into list of strings of sql results that are formated through template
		
		# make sure sql_outp_col_order doesn't have references to tables,
		# <table>.<column> doesn't work with Templates, '.' is not working
		sql_outp_col_order = adjust_sql_sel_outp_col_order(sql_outp_col_order)

		# keep track of the results columns' order and their corresponding indexes
		# in this dict
		identifier_order = dict()
		
		for identifier in self.formatter[table].templ.get_identifiers():
			if identifier in sql_outp_col_order:
				identifier_order.update({identifier: sql_outp_col_order.index(identifier)})

		# now we can replace the sql_outp by mapping with identifier_order
		lines = list()

		for line in sql_outp:
			
			# TODO integrate field width and ljust into the Formatter class intialization
			# misc intervention so we can replace loglvl with a ljust loglvl
			if "loglvl" in identifier_order:
				line = adjust_sql_sel_outp_loglvl(line, identifier_order)

			mapper = {ident: line[identifier_order[ident]] for ident in identifier_order}

			if safe:
				lines.append(self.formatter[table].apply_safe(mapper))
			else:
				s = self.formatter[table].apply(mapper)
				if s is not None:	
					lines.append(s)

		return lines


	def init_scheme(self) -> None:
		for table in self.scheme.schemes:
			re = self._exec_com(self.scheme.schemes[table].raw_schema)			
			
			if isinstance(re, list):
				self.__class__._log.debug(f"initialized '{table}' in {short(self.dbfp)}")

				# TODO validate table has all columns that are in self.scheme.schemes[table].columns
				# condition set() == set(self.scheme.schemes[table].columns)
				# if not the same, make set.difference() and check needed columns are FOREIGN KEY
				# if so, build FOREIGN KEY sql and add to com 
				# do sql to add needed column through exec com

			else:
				self.__class__._log.error(f"failed initialization for table '{table}' {shortb(self.scheme.schemes[table].raw_schema)}")				


	def open_db(self, dbfp:str="", read_only:bool=False, attempt:int=0, max_retry:int=3) -> Union[sqlite3.Connection, None]:
		if len(dbfp) == 0:
			dbfp = self.dbfp

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

		if not read_only and self.scheme.finalized:
			self.init_scheme()

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
