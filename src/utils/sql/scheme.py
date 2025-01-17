# sql schemer
'''
this will automatically declare tables and the relation between
the columns/foreign keys with other tables' keys
'''
from typing import Union

from hkeep.error import tb
from hkeep.logger import get_logger
from utils.sql.schema import Schema


class Scheme:

	_log = get_logger(__name__)


	def __init__(self, tables:set) -> None:
		if not isinstance(tables, set):
			raise Exception('init of Scheme with tables:set invalid type')

		self.tables = tables
		self.dependancies = {
								"unknown_foreign_of": list()
							}
		self.schemes = dict()


	def add_table(self, schema:Union[Schema, None]=None, table:str='') -> bool:
		try:
			schema_avail = False

			if isinstance(schema, str):
				schema = Schema(schema)
				
				if schema.table != table:

					if len(table) == 0:
						self.tables.add(schema.table)
				
					else:
						raise Exception('called add_table table not corresponding to schema table')
				
				self.schemes.update({schema.table: schema})
				schema_avail = True

			elif schema is not None:
				raise Exception('called add_table with schema:Union[Schema, None] invalid type')

			if len(table) > 0 and table not in self.tables:	
				self.tables.add(table)

		except Exception as E:
			self.__class__._log.error(tb(E))

			return False

		else:

			if not schema_avail:	
				return True

			else:
				return self.add_schema(schema)


	def add_schema(self, schema:Schema) -> bool:

		_added_table = False

		try:

			if schema.table not in self.tables:
				self.tables.add(schema.table)
				_added_table = True

			for line in schema.schema:
				line_w = line.split()

				# detect foreign keys to implement in dependancies
				if line_w[0].upper() == "FOREIGN":
					self.__class__._log.debug(f"running schemes.update with {schema.table, schema}")
					self._apply_schema_foreign_dependancy(schema.table, line_w)

				# detect column searched lines by unknown dependancies 
				elif len(self.dependancies["unknown_foreign_of"]) > 0:
					# build own value
					value = schema.table+'.'+line_w[0]

					if value in self.dependancies["unknown_foreign_of"]:
						self.dependancies["unknown_foreign_of"].remove(value)
						self.__class__._log.debug(f"removed from unknown_foreign_of '{value}'")

				#self.__class__._log.debug(f"worked on '{line}'")


		except Exception as E:
			self.__class__._log.error(tb(E))
			# undo changes to self.tables, if changed
			if _added_table:
				self.tables.remove(schema.table)

			return False

		else:
			self.schemes.update({schema.table: schema})

			return True		


	def _apply_schema_foreign_dependancy(self, table:str, line_w:list) -> None:
		key = table+'.'+line_w[1][4:-1]
		value = line_w[3].replace('(', '.').strip('),')

		backup = {key: self.dependancies[key]} if key in self.dependancies else None

		self.dependancies.update({key: value})

		# in case the column to which this foreign key references
		# is not yet in self.schemes[table]
		# first look for table, if unknown -> put value in unknown_foreign_of
		ref_table, ref_col = value.split('.')
		if ref_table not in self.schemes:
			self.dependancies["unknown_foreign_of"].append(value)
			self.__class__._log.debug(f"appended to  unknown_foreign_of '{value}'")
		# table is there, look for specific column
		elif not ref_col in self.schemes[ref_table].raw_schema:
			# table is in dict self.schemes but without the referenced column
			# reset the old state of dependancies
			if backup is not None:
				self.dependancies.update(backup)

			# raise	
			raise Exception(f'schema foreign key "{key}" references "{value}", but the referenced table has been processed without said column "{ref_col}')


	def finalize(self, log_true=True) -> bool:

		# two checks in total

		# first precheck the length equality as optimization
		if len(self.tables) == len(self.schemes.keys()):

			# now check if self.tables == set(self.schemes.keys())
			# to know if the same tables have been provided with a
			# schema that have been declared
			if self.tables == set(self.schemes.keys()):
				# first condition is valid
				# now also check if there are no unknown in self.dependancies
				if len(self.dependancies["unknown_foreign_of"]) > 0:
					self.__class__._log.warning(f"can't finalize, Scheme obj still has unfound dependancy pairs: {self.dependancies["unknown_foreign_of"]}")

					return False

				else:
					# everything seems fine
					if log_true:
						l_depend = len(self.dependancies.keys())-1
						self.__class__._log.info(f"Scheme obj finalized with {len(self.tables)} schemes and {l_depend} dependanc{'ies' if l_depend != 1 else 'y'}")

					return True

			else:
				self.__class__._log.warning(f"can't finalize, provided Scheme obj with different tables than the tables schemes have been provided for")

				return False

		else:
			self.__class__._log.warning(f"can't finalize, provided Scheme obj with different amount of tables than schemes")
			self.__class__._log.debug(f"{self.tables} vs {list(self.schemes.keys())}")

			return False
