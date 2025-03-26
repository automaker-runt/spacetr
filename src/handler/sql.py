# sql handler
import sqlite3
import time
from threading import get_ident
from typing import Union

from fsys import rename
from handler.conn import ConnectionHandler
from hkeep.error import tb
from hkeep.log.logger import get_logger
from hkeep.log.misc import adjust_sql_sel_outp_loglvl, adjust_sql_sel_outp_col_order
from utils.dicts import create 
from utils.sql.conn import Connection
from utils.sql.scheme import Schemers
from utils.sql import strings
from utils.strings.format import Formatter, DeFormatter
from utils.strings.shorten import short, shortb


class SqlHand:

	_log = get_logger(__name__)


	def __init__(	self,
					Scheme:Schemers,
					dbfp:str,
					Deformatter: Union[dict, None]=None,
					Formatter: Union[tuple, None]=None,
					ConnHandler: Union[ConnectionHandler, None]=None) -> None:
		
		# check for Scheme successfull finalization
		if not Scheme.finalized and not Scheme.finalize():
			self.Scheme = Schemers(tables=Scheme.tables)
			self.__class__._log.warning(f"initialized SqlHand without finalized Schemers obj; self.Scheme.add_schema & self.Scheme.finalize & run self.init_DB needed")
		else:
			self.Scheme = Scheme
		
		self.dbfp = dbfp

		# check for valid Formatter types and set self.formatter
		# Formatter argument needs to be either 2 level tuples ((table, Formatter), (table, Formatter))
		# or a simple tuple (table, Formatter) with table being a str
		# and Formatter being the class Formatter
		self.formatter = dict()
		if Formatter is None:
			pass
		elif isinstance(Formatter, tuple):
			if len(Formatter) > 0 and isinstance(Formatter[0], tuple):
				for form in Formatter:
					self.formatter.update({form[0]: form[1]})

			elif len(Formatter) > 0 and isinstance(Formatter[0], str):
				self.formatter.update({Formatter[0]: Formatter[1]})

			else:
				self.__class__._log.warning(f"initialized SqlHand with wrong Formatter type or invalid structure")
		else:
			self.__class__._log.warning(f"initialized SqlHand with wrong Formatter type")
		
		# Deformatter is supposed to also be table boound
		# needs to be given as dict, with key specifying table
		# and value the DeFormatter Obj
		if isinstance(Deformatter, dict):
			self.deformatter = Deformatter
		else:
			self.deformatter = dict()

		# check ConnHandler
		if ConnHandler is None:
			self.ConnHandler = ConnectionHandler(self.dbfp)
		elif isinstance(ConnHandler, ConnectionHandler):
			self.ConnHandler = ConnHandler
		else:
			self.__class__._log.warning(f"initialized SqlHand with wrong type for ConnHandler: {type(ConnHandler)}")
			self.ConnHandler = ConnectionHandler(self.dbfp)

		self.journal_mode = None
		self.ConnHandler._add_conn(open_conn=False, read_only=False, persist=True)


	def ins(self, table:str, inp: Union[list, str], extras: Union[dict, None]=None, **entryargs) -> bool:
		
		multiple_ins = False
		# check inp for type and structure (multiple lines or just one?)
		if isinstance(inp, list):
			if len(inp) == 1:
				if isinstance(inp[0], str):
						# deformat the string to a list of strings for the
						# single line of inp
						if table in self.deformatter:
							inp = self.deformatter[table].apply(inp[0])

						'''
						inactive due to weird behaviour, have to trust that no ins will be called with wrong formatted inp and no table in deformatter
						'''
						# else:
						# 	self.__class__._log.error(f"ins inp is list with one str item but no deformatter given for table '{table}', len inp({len(inp)}), len cols{len(self.Scheme.schemes[table].columns)}")

						# 	return False

				else:
					pass
					# self.__class__._log.error(f"ins inp single list item TypeError not being str: {type(inp[0])}")

					# return False
				
			elif len(inp) > 1 and (isinstance(inp[0], Union[str, int]) or isinstance(inp[-1], Union[str, int])):
				# a list with many strings giving values for one line
				if table in self.deformatter:
					inp = self.deformatter[table].apply(inp)
				

			elif len(inp) > 1 and isinstance(inp[0], list):
				# a list containing lists, where each list is one line
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

			'''
			inactive due to weird behaviour, have to trust that no ins will be called with wrong formatted inp and no table in deformatter
			'''
			# else:
			# 	self.__class__._log.error(f"ins inp being a str but no deformatter given for table '{table}'")

			# 	return False

		else:
			self.__class__._log.error(f"ins TypeError due to inp not being a list or str: {type(inp)}")

			return False

		column_order = self.Scheme.schemes[table].columns

		if not multiple_ins:

			return self._ins_one(table, inp, column_order, extras=extras, **entryargs)

		else:
			result = True
			for i in inp:
				if not self._ins_one(table, i, column_order, extras=extras, **entryargs):
					result = False

			return result


	def _ins_one(self, table:str,
						one:list,
						col_order:list,
						extras: Union[dict, None]=None,
						no_duplicates:bool=True,
						**entryargs) -> bool:
		
		Conn = self.get_conn(read_only=False)

		if not Conn.open_status:
			self.__class__._log.critical("_ins_one Conn.open_status 'False', aborting")

			return False

		if "id" in col_order:
			# need copy, or else at second insert, column id is missing and
			# throws over len(self.Scheme.schemes[ref_tbl].columns)
			# since col_order references that here 
			col_order = col_order.copy()
			col_order.remove("id")

		# have to process every column of the table for INSERT
		for col in col_order:

			_tbl_cl_comb = f"{table}.{col}"
			# except PRIMARY KEY AUTOINCREMET
			if col.lower() == "id":
				continue
			
			# check for dependancies
			elif _tbl_cl_comb in self.Scheme.dependancies:				

				# lookup col with it's specific col_order.index() as one[index]' value
				# in specific table
				# if value is in that table, grab the id and replace one[index]' value with id
				# if it is not in there, INS, grab then id and replace one[index]' value with id
				# do this for all cols if in self.Scheme.dependancies

				_indx = col_order.index(col)
				if isinstance(one, list) and len(one) > _indx:
					_val = one[_indx]
					# if type in one is other than str/int make it be
					if not isinstance(_val, Union[str, int, None]):
						_val = str(_val)
				else:
					self.__class__._log.error(f"_ins_one one is either not a list or len of it is smaller than _indx")
					self.__class__._log.info(f"_ins_one type(one):{type(one)} && len(one)({len(one)}), _indx({_indx}), one({one}), col_order({col_order})")

					return False

				ref_tbl_cl_comb = self.Scheme.dependancies[_tbl_cl_comb]
				ref_tbl = ref_tbl_cl_comb[:ref_tbl_cl_comb.find('.')]
				ref_cl_id = ref_tbl_cl_comb[ref_tbl_cl_comb.find('.')+1:]
				ref_cl_name = f"{ref_tbl[1:]}"

				com = f"SELECT id FROM {ref_tbl} WHERE {ref_cl_name}=?;"
				com_var = (_val,)
				
				self.__class__._log.debug(f"_ins_one sel id from '{ref_tbl}' WHERE {ref_cl_name}={_val}")
				re = self.sel(com, com_var, _format=False, Conn=Conn)

				# check for results, to know if _val already in there
				if re is not None and len(re) > 0:
					_id = re[0][0]
					one[_indx] = _id
					self.__class__._log.debug(f"_ins_one sel id from '{ref_tbl}' WHERE {ref_cl_name}={_val} returned id={_id}")

				# if error occured re is None
				elif re is None:
					self.__class__._log.error(f"_ins_one value({_val}) lookup in '{ref_tbl}.{ref_cl_name}' returned None")
					self.__class__._log.info(f"_ins_one self.Scheme.dependancies: {self.Scheme.dependancies}")

					return False

				# expect len to be 0, aka not in there
				else:
					self.__class__._log.debug(f"_ins_one sel from '{ref_tbl}' WHERE {ref_cl_name}={_val} returned len 0")

					# need to check if ref_tbl has column "updated"
					if "updated" in self.Scheme.schemes[ref_tbl].columns and len(self.Scheme.schemes[ref_tbl].columns) == 3:
						re_ins = self.ins(ref_tbl, [_val, int(time.time())])
					elif ("updated" in self.Scheme.schemes[ref_tbl].columns and 
							len(self.Scheme.schemes[ref_tbl].columns) > 3):
						# ref_tbl has more columns than ref_cl_name and "updated"
							
						original_columns = self.Scheme.schemes[ref_tbl].columns.copy()
						if "id" in original_columns:
							original_columns.pop(0)

						if extras is not None and ref_tbl in extras: # condition to be able to do insert in ref_tbl with more than just 2 values _val and int(time.time())
							
							original_columns = original_columns[1:]
							complete_vals = [_val]
							complete_vals.extend([extras[ref_tbl][i] for i in original_columns])

							re_ins = self.ins(ref_tbl, complete_vals)

						else:
							# do as last resort a reduced insert, leaving NULL values, through _ins_one by
							# explicitly only giving _val for whatever the column name is and int(time.time()) for update column
							min_columns = [original_columns[0], original_columns[-1]]

							re_ins = self._ins_one(ref_tbl, [_val, int(time.time())], min_columns)
							
							if not re_ins:
								self.__class__._log.critical(f"_ins_one failed insert into ref_tbl({ref_tbl}) {ref_cl_name}={_val} because ref_tbl needs {len(self.Scheme.schemes[ref_tbl].columns)-1} values and wasn't provided in extras argument")

					else:
						re_ins = self.ins(ref_tbl, [_val])
						
					self.__class__._log.debug(f"_ins_one insert into ref_tbl({ref_tbl}) {ref_cl_name}={_val} returned {re_ins}")

					if re_ins:
						self.__class__._log.debug(f"_ins_one insert into '{ref_tbl}' {ref_cl_name}={_val} successful")
						# now need to grab id
						re = self.sel(com, com_var, _format=False, Conn=Conn)

						# re should have len and be list now
						if re is None or len(re) == 0:
							self.__class__._log.error(f"_ins_one sel from '{ref_tbl}' WHERE {ref_cl_name}={_val} returned NoneType or len 0 after specific insert")

							return False

						# insert+select success
						else:
							_id = re[0][0]
							one[_indx] = _id
							self.__class__._log.debug(f"_ins_one after ins sel id from '{ref_tbl}' WHERE {ref_cl_name}={_val} returned id={_id}")
						
					else:
						self.__class__._log.error(f"_ins_one failed insert into '{ref_tbl}' {ref_cl_name}={_val}")

						return False

		# until here one has been redacted and values should have been replaced with the
		# ids of the foreign keys

		# normalize values, get where x=?, ... part
		try:	
			where, ins_dict = create.dict_sql_ins(col_order, one)
		except Exception as E:
			raise E

		
		if no_duplicates:
			# make sure our table has id column:
			if self._has_table_column(table, 'id', Conn):
				sel_col = 'id'
				re_sel_id = True
			else:
				sel_col = '*'
				re_sel_id = False		

			# sel what we just want to insert, if it returns len > 0, we don't insert
			re_sel = self.sel(f"SELECT {sel_col} FROM {table} WHERE {where};", tuple(ins_dict.values()), _format=False, Conn=Conn)
		
		# sometimes we want duplicates
		else:
			re_sel = tuple()

		if len(re_sel) == 0:

			com = strings.get_str_sql_ins(table, ins_dict)

			if not isinstance(self._exec_com(Conn, com, tuple(ins_dict.values())), list):
				self.__class__._log.error(f"_ins_one failed insert in {table} {[(i, j) for i,j in ins_dict.items()]}")

				return False

			else:
				self.__class__._log.debug(f"_ins_one inserted in {table} {[(i, j) for i,j in ins_dict.items()]}")

				# now in case this is an entry with entryargs
				if len(entryargs) > 0:
					# now we need to act on the entryargs
					di = entryargs.copy()

					# get the table we need to insert the entryargs into
					# should only be one key starting with first char '_'
					table_entryargs = [i for i in di.keys() if i[0] == '_'][0]
					table_entryargs_colnames = di.pop(table_entryargs)
					# all entries in di are now actual values we need to insert
					# keys go into [0] and values into [1] of table_entryargs_colnames
					
					# all remaining columns for table_entryargs are foreign keys
					# these are ids we need for table_entryargs
					# we get them from self.Scheme.dependancies
					dependancies = [i for i in self.Scheme.dependancies if f"{table_entryargs}." in i]
					# fill table_entryargs_colnames with dependancies without table_entryargs
					# so we have the whole set of column names of our table the entryargs go into
					table_entryargs_colnames.extend([i[i.find('.')+1:] for i in dependancies])

					# get the info of the table(s) holding foreign keys and their columns
					fk_tabl_col_comb = list()
					fk_tables = list({v[:v.find('.')] for k, v in self.Scheme.dependancies.items() if table_entryargs in k and fk_tabl_col_comb.append(v) is None})

					fk_values = list()

					# sel from all foreign keys tables to obtain the needed foreign key value
					for fk_combo in fk_tabl_col_comb:
						t = fk_combo[:fk_combo.find('.')]
						col = fk_combo[len(t)+1:]
						re_fk_val = self.sel(f"SELECT {col} FROM {t} WHERE {where};", tuple(ins_dict.values()), _format=False, Conn=Conn)

						if len(re_fk_val) == 0:
							self.__class__._log.error(f"_ins_one failed obtaining re_fk_val from '{t}.{col}' to insert in {table_entryargs}")

							return False

						else:
							fk_values.extend(list(re_fk_val[0]))

					table_entryargs_vals = list()

					for k, v in di.items():
						entry = [k, v]
						entry.extend(fk_values)
						table_entryargs_vals.append(entry)

					for insert_vals in table_entryargs_vals:
						where, ins_dict = create.dict_sql_ins(table_entryargs_colnames, insert_vals)

						if len(self.sel(f"SELECT {strings.get_str_sql_sel_cols(ins_dict)} FROM {table_entryargs} WHERE {where};", tuple(ins_dict.values()), _format=False, Conn=Conn)) == 0:

							com = strings.get_str_sql_ins(table_entryargs, ins_dict)

							# insert into table_entryargs through direct _exec_com
							# not through ins or _ins_one, because they would try to get a 'og'-value from table 'log'! Trying to cut first char "_" and look for that column
							if not isinstance(self._exec_com(Conn, com, tuple(ins_dict.values())), list):
								self.__class__._log.error(f"_ins_one failed insert in {table_entryargs} {[(i, j) for i,j in ins_dict.items()]}")

								return False

						else:
							self.__class__._log.error(f"_ins_one failed insert in '{table_entryargs}' because entry already there, {tuple(ins_dict.values())}")

							return False


				return True

		else:
			# case for debug -> more details, info -> less details
			if self.__class__._log.isEnabledFor(10):	
				if re_sel_id:	
					self.__class__._log.debug(f"_ins_one prevented duplicate insert into {table} of columns{tuple(ins_dict.keys())} and values{tuple(ins_dict.values())}, their id: {re_sel}")
				else:
					self.__class__._log.debug(f"_ins_one prevented duplicate insert into {table} of columns{tuple(ins_dict.keys())} and values{tuple(ins_dict.values())}")
			else:
				if re_sel_id:	
					self.__class__._log.warning(f"_ins_one prevented duplicate insert into {table}, value's id: {re_sel}")
				else:
					self.__class__._log.warning(f"_ins_one prevented duplicate insert into {table}")

			return False


	def updt(self, table:str, cols: Union[tuple, list], vals: Union[tuple, list], unique:dict) -> bool:

		# checking type cols
		if all(not isinstance(cols, i) for i in (tuple, list)):
			self.__class__._log.error(f"updt TypeError due to cols not being a list or tuple: {type(cols)}")

			return False

		# checking type vals
		elif all(not isinstance(vals, i) for i in (tuple, list)):
			self.__class__._log.error(f"updt TypeError due to vals not being a list or tuple: {type(vals)}")

			return False

		elif not isinstance(unique, dict):
			self.__class__._log.error(f"updt TypeError due to unique not being a dict: {type(vals)}")

			return False

		# check for same len
		elif len(vals) != len(cols):
			self.__class__._log.error(f"updt ValueError due to different len in cols and vals: {len(cols)} {len(vals)}")

			return False

		# get conns
		Conn = self.get_conn(read_only=False, persist=True)

		# to prevent Conn being left open, finally block needed
		try:	
			if not Conn.open_status:
				self.__class__._log.critical("updt Conn.open_status 'False', aborting")

				return False

			# make both lists
			if isinstance(cols, tuple):
				cols = list(cols)
			if isinstance(vals, tuple):
				vals = list(vals)

			if "id" in cols:
				cols.remove("id")

			# go through cols and make sure they are in 
			# the right <table>.<col> format, col should also be the right one

			# process it for UPDATE
			for indx, col in enumerate(cols.copy()):

				# look for a possible foreign key version of col in the table in Schema.columns
				if f"{col}_id" in self.Scheme.schemes[table].columns:
					real_col = f"{col}_id"
				
				# maybe col is the original column name
				elif col in self.Scheme.schemes[table].columns:
					real_col = col

				else:
					# get next best possible real_col and log it as INFO
					li = [i for i in self.Scheme.schemes[table].columns if col in i]
					real_col = next(iter(li), None)
					if real_col is None:
						self.__class__._log.error(f"updt failed to find real_col for '{col}' in {table}")
						return False
					self.__class__._log.debug(f"updt guessed the real_col of '{col}' is '{real_col}' out of {li}")

				cols[indx] = real_col
				tabl_real_col_comb = f"{table}.{real_col}"

				# check dependancy
				if tabl_real_col_comb in self.Scheme.dependancies:

					ref_tbl, ref_col = self.Scheme.dependancies[f"{table}.{real_col}"].split(".")

					val = vals[indx]
					# check the ref_tbl for the val
					com, com_val = f"SELECT {ref_col} FROM {ref_tbl} WHERE {ref_tbl[1:]}=?", (val,)

					self.__class__._log.debug(f"updt sel id from '{ref_tbl}' WHERE {ref_tbl[1:]}=? {(val,)}")
					re = self.sel(com, com_val, _format=False, Conn=Conn)

					# check for results, to know if _val already in there
					if re is not None and len(re) > 0:
						self.__class__._log.debug(f"updt sel from '{ref_tbl}' WHERE {ref_tbl[1:]}={val} returned {re}")
						_id = re[0][0]
						vals[indx] = _id

					# if error occured re is None
					elif re is None:
						self.__class__._log.error(f"updt failed sel from '{ref_tbl}' WHERE {ref_tbl[1:]}={val} returned None")
						self.__class__._log.debug(f"updt self.Scheme.dependancies: {self.Scheme.dependancies}")

						return False

					# expect len to be 0, aka not in there
					else:
						self.__class__._log.debug(f"updt sel from '{ref_tbl}' WHERE {ref_tbl[1:]}={val} returned len 0")

						# insert val into that table
						re_ins = self.ins(ref_tbl, [val]) # TODO make it use all columns in case the ref_tbl has more than just 2 columns id and value
						self.__class__._log.debug(f"updt insert into ref_tbl({ref_tbl}) {ref_tbl[1:]}={val} returned {re_ins}")

						# True on success
						if re_ins:
							self.__class__._log.debug(f"updt insert into '{ref_tbl}' {ref_tbl[1:]}={val} successful")
							# now need to grab id
							re = self.sel(com, com_val, _format=False, Conn=Conn)

							# re should have len and be list now
							if re is None or len(re) == 0:
								self.__class__._log.error(f"updt sel '{com}', {com_val} returned NoneType or len 0 after specific insert")

								return False

							# insert+select success
							else:
								_id = re[0][0]
								vals[indx] = _id
								self.__class__._log.debug(f"updt after ins sel id from '{ref_tbl}' WHERE {ref_tbl[1:]}={val} returned id={_id}")
							
						else:
							self.__class__._log.error(f"updt failed insert into '{ref_tbl}' {ref_tbl[1:]}={val}")

							return False


			# until here vals and cols have been redacted and values and columns should have been replaced with the
			# ids of the foreign keys and with the true column names

			where, where_dict = create.dict_sql_sel(list(unique.keys()), list(unique.values()))
			set_, set_dict = create.dict_sql_updt(cols, vals)

			com_vals = list()
			com_vals.extend(set_dict.values())
			com_vals.extend(where_dict.values())

			# UPDATE the columns in that row using unique
			com = f"UPDATE {table} SET {set_} WHERE {where};"

			self.__class__._log.debug(f"updt '{com}', {com_vals}")

			if not isinstance(self._exec_com(Conn, com, tuple(com_vals)), list):
				self.__class__._log.error(f"updt failed in {table} to set {set_}")

				return False

			else:
				self.__class__._log.debug(f"updt in {table} set {set_}")

				return True

		except Exception as E:
			self.__class__._log.critical(f"updt unexpected Error, {tb(E)}")

			return False


	def sel(self, com:str, com_var: Union[tuple, None]=None, _format:bool=True, Conn: Union[Connection, None]=None) -> list:
		# assure reading Connection
		if Conn is None:
			Conn = self.get_conn()
			if not Conn.open_status:
				self.__class__._log.critical("sel Conn.open_status 'False', aborting")

				return list()

		# assure com_var is at least empty tuple
		if com_var is None:
			com_var = tuple()

		com = com.strip().replace('\n', '')
		
		l_com = com.split()
		# find table name by looking for the next item after "FROM"
		table = l_com[l_com.index("FROM")+1].strip(';,')
		# find selected columns by looking for the next item after "SELECT"
		# until index of "FROM"
		# can't look it up in self.Scheme.schemes[table].columns, because not all may be selected
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
			value = self.Scheme.dependancies[key]
			left_join_block = f'\nLEFT JOIN {value[:value.find(".")]} ON {key} = {value}'
			com_str += left_join_block

		# now finish com_str by adding any WHERE/LIMIT/ORDER BY statements
		com_str += '\n'+' '.join(l_com[l_com.index("FROM")+2:])
		
		# assure sql statement is ending with ";"
		com_str = self._check_com_str_semic(com_str)
		self.__class__._log.debug(f"sel com_str: '{com_str}'")

		re = self._exec_com(Conn, com_str, com_var)

		# check validity of re
		if isinstance(re, list) and len(re) > 0:
			# apply Formatter if available			
		
			# check if we want to format or not
			if _format:	
				# for when table is in self.formatter dict
				if isinstance(self.formatter, dict) and table in self.formatter:
				
					self.__class__._log.debug("sel applying Formatter")
					return self.apply_formatter(table=table,
												sql_outp=re,
												sql_outp_col_order=columns)

				# for when self.formatter is None and in case self.formatter is dict but table not in it
				elif self.formatter is None or (isinstance(self.formatter, dict) and not table in self.formatter):
					self.__class__._log.debug("sel not applying Formatter")

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


	def del_simple(self, com:str, com_var_tup:tuple=tuple(), Conn: Union[Connection, None]=None) -> bool:
		# only wraps _exec_com to get a Conn or apply given Conn
		# then just passes com and com_var_tup to _exec_com

		# get or set Conn
		Conn = self.get_conn(read_only=False) if Conn is None else Conn

		if not Conn.open_status:
			self.__class__._log.critical("_ins_one Conn.open_status 'False', aborting")

			return False

		if not isinstance(self._exec_com(Conn, com, com_var_tup), list):
			self.__class__._log.error(f"del_simple failed delete '{com}, {com_var_tup}'")

			return False

		else:
			self.__class__._log.debug(f"del_simple deleted with '{com}, {com_var_tup}'")

			return True


	def _exec_com(self, Conn:Connection, com:str, com_var_tup:tuple=tuple()) -> Union[list, bool]:
		if Conn.open_status:	
			cur = Conn.Conn.cursor()
		else:
			self.__class__._log.critical("_exec_com Conn.Conn is None, aborting")

			return False
		
		try:	
			# execute com with com_var_tup if needed
			if len(com_var_tup) > 0:
				cur.execute(com, com_var_tup)
			else:
				cur.execute(com)

		except Exception as E:
			self.__class__._log.error(f"_exec_com failed sql command({com}, {com_var_tup}), {tb(E)}")

			return False

		else:
		
			re = cur.fetchall()

			if self.__class__._log.isEnabledFor(10):
				com_var_tup_str = f", {com_var_tup}" if len(com_var_tup) > 0 else ""
				re_snippet = f" resulting in {len(re)} lines, 1st one: {shortb(re[0])}" if len(re) > 0 else ""
				self.__class__._log.debug(f"executed sql command '{com}'{com_var_tup_str}{re_snippet}")

			# TODO put this one in ins and only commit when no error occured on the way, else rollback
			if not Conn.read_only:
				Conn.Conn.commit()

			# make sure re is a list, even empty, but has to be list
			if not isinstance(re, list):
				return list()
			else:
				return re

		finally:
			cur.close()
			# also close reading connections
			if not Conn.persist and not self.ConnHandler.remove_conn(Conn):
				self.__class__._log.error(f"_exec_com failed removing Connection '{Conn.key_id}' from ConnectionHandler.conns")


	def _grab_dependancies(self, table:str, columns:list) -> list:
		dependancies = list()

		# checking if table (from select) is a table in schemes
		# and is referenced to from a foreign key
		if table in self.Scheme.schemes:
			# look whether select mentions columns with dependancy
			for col in columns:
				col = self.Scheme.__class__._col_redact_from_table(col)
				# now we build from columns mentioned in select their
				# <table>.<column> equivalent applying naming convention
				if f"{table}.{col}_id" in self.Scheme.dependancies:
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


	def _has_table_column(self, table:str, column:str, Conn:Connection) -> bool:
		# returns True if column exists in table, else returns False

		com = f"SELECT COUNT(*) AS CNTREC FROM pragma_table_info('{table}') WHERE name='{column}'"
		re = self._exec_com(Conn, com)[0][0]
		if re > 0:
			return True
		else:
			return False


	def use_formatter(self, Formatter:Formatter, table:str=str()) -> bool:
		table = table.strip().lower()

		if len(self.Scheme.tables) == 1:
			saved = self.Scheme.tables.copy().pop().strip().lower()
			if len(table) > 0 and table != saved:
				self.__class__._log.warning(f"gave use_formatter different table '{table}' than the single table in self.Scheme.tables: '{saved}'")
				self.formatter[saved] = Formatter
			else:	
				self.formatter[saved] = Formatter

			table = saved

		elif len(self.Scheme.tables) > 1 and len(table) > 0:
			self.formatter[table] = Formatter

		elif len(self.Scheme.tables) >= 0 and len(table) == 0:
			self.__class__._log.warning(f"didn't select specific table from self.Scheme.tables in use_formatter to use Formatter with")

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


	def init_DB(self, Conn:Connection) -> None:
		
		# get journal_mode
		if self.journal_mode is None:	
			
			re = self._exec_com(Conn=Conn, com="PRAGMA journal_mode;")
			if isinstance(re, list):
				self.journal_mode = re[0][0].upper()
				self.__class__._log.debug(f"grabbed pragma journal_mode '{self.journal_mode}' through '{Conn.key_id}' from {short(self.dbfp)}")

			else:
				self.__class__._log.error(f"init_DB failed grabbing pragma journal_mode from {short(self.dbfp)}")

		# set journal_mode
		if self.journal_mode.upper() != "WAL" and not Conn.read_only and Conn.key_id == "main1":
			# set journal_mode
			re = self._exec_com(Conn=Conn, com="PRAGMA journal_mode=WAL;")
			if isinstance(re, list):
				self.__class__._log.debug(f"grabbed pragma journal_mode from {short(self.dbfp)}")
				self.journal_mode = re[0][0].upper()

			else:
				self.__class__._log.error(f"init_DB failed grabbing pragma journal_mode from {short(self.dbfp)}")

		# create tables
		if not Conn.read_only and Conn.key_id == "main1":	
			error = False

			# runs the sql CREATE TABLE commands
			for table in self.Scheme.schemes:
				re = self._exec_com(Conn=Conn, com=self.Scheme.schemes[table].raw_schema)			
				
				if isinstance(re, list):
					self.__class__._log.debug(f"initialized '{table}' in {short(self.dbfp)}")

					# TODO validate table has all columns that are in self.Scheme.schemes[table].columns
					# condition set() == set(self.Scheme.schemes[table].columns)
					# if not the same, make set.difference() and check needed columns are FOREIGN KEY
					# if so, build FOREIGN KEY sql and add to com 
					# do sql to add needed column through exec com

				else:
					self.__class__._log.error(f"init_DB failed initialization for table '{table}' {shortb(self.Scheme.schemes[table].raw_schema)}")
					error = True

			# create views if present
			if not error: 
				if len(self.Scheme.views) > 0:
					for view in self.Scheme.views:
						re = self._exec_com(Conn=Conn, com=view)

						if isinstance(re, list):
							self.__class__._log.debug(f"initialized view in {short(self.dbfp)}")

						else:
							self.__class__._log.error(f"init_DB failed initialization of a view: {view}")

			else:
				self.__class__._log.warning(f"init_DB didn't execute possible views because of error in initialization of table(s)")


	def get_conn(self, read_only:bool=True, persist: Union[bool, None]=None) -> Union[Connection, None]:
		
		if persist is None:
			persist = not read_only

		# check if there is a suitable conn already opened by this thread
		suitable_conn_id = list()
		# check for persist True, thread_id to match this thread and then append
		if any(True for i in self.ConnHandler.conns.values() if i.persist and i.thread_id == get_ident() and suitable_conn_id.append(i.key_id) is None):
			self.__class__._log.debug(f"get_conn found suitable Conn '{suitable_conn_id[0]}'")
			
			return self.ConnHandler.conns[suitable_conn_id.pop(0)]

		else:
			# need to pass ConnHandler init_DB on read_only=False get_conn
			return self.ConnHandler.get_conn(read_only, 
									self.journal_mode, 
									init_DB=self.init_DB,
									persist=persist)


	def close(self):
		for Conn in list(self.ConnHandler.conns.values()).copy():
			re = self.ConnHandler.remove_conn(Conn)
			self.__class__._log.debug(f"attempted closing Connection '{Conn.key_id}' to DB {short(Conn.dbfp)}, result: {re}")


	def new_dbfp(self, dbfp:str):
		# renames current file to last increment+1
		# creates new blank DB with same filename before renaming

		self.close()
		# rename old files with dbfp (also shm and wal files)
		if not rename.sqlite_files(self.dbfp, dbfp):
			self.__class__._log.error(f"new_dbfp failed renaming {short(self.dbfp)}")

			raise Exception("Failed creating new DB")

		# create new DB file without number
		self.__init__(self.Scheme, self.dbfp)
		self.__class__._log.info(f"created new DB {short(self.dbfp)} and renamed old DB to {short(dbfp)}")


	def __del__(self):
		# check for attr, in case exception happened in __init__
		if hasattr(self, "ConnHandler"):	
			self.__class__._log.debug(f"deleting SqlHand obj and closing DBs {[(i.key_id, short(i.dbfp)) for i in self.ConnHandler.conns.values()]}")

		deleted = list()

		# check for attr, in case exception happened in __init__
		if hasattr(self, "ConnHandler"):	
						
			for Conn in self.ConnHandler.conns.values():
				
				item = [Conn.key_id]

				try:	
					if Conn.open_status:
						item.append("open_status True")

						if not Conn.close_DB():
							item.append(False)
							item.append(Conn.close_DB(force=True))
						else:
							item.append(True)

					else:
						item.append("open_status False")

				except sqlite3.ProgrammingError as PE:
					# maybe it happened because of DB already closed
					if "Cannot operate on a closed database." in str(PE):
						self.__class__._log.warning(f"unsuccessful closing Connection '{Conn.key_id}' to DB {short(Conn.dbfp)}, {tb(PE)}")

					else:
						self.__class__._log.error(f"failed closing Connection '{Conn.key_id}' to DB {Conn.dbfp}, {tb(PE)}")

						raise PE

				finally:
					deleted.append(tuple(item))
		
		if len(deleted) > 0:
			self.__class__._log.warning(f"attempt closing through __del__ function: {deleted}")
