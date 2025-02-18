import sqlite3
from collections.abc import Callable
from threading import get_ident
from typing import Union

from hkeep.log.logger import get_logger
from utils.sql.conn import Connection


class ConnectionHandler:

	_log = get_logger(__name__)


	def __init__(self, dbfp:str):
		self.conns = dict()
		self.dbfp = dbfp


	def _add_conn(self, read_only:bool=False, open_conn:bool=True, persist:bool=True) -> Union[Connection, None]:
		
		# starting name is either main1 or Conn1
		n_conn_name = self._get_new_Conn_name("Conn" if read_only else "main")
		Conn = Connection(self.dbfp, read_only=read_only, open_conn=open_conn, persist=persist, key_id=n_conn_name)
		
		self.conns.update({n_conn_name: Conn})

		return Conn


	def remove_conn(self, Conn:Connection, pragma:str='') -> bool:
		# type check Conn
		if not isinstance(Conn, Connection):
			self.__class__._log.error(f"remove_conn called with wrong Conn type: {type(Conn)}")

			return False

		if not Conn.read_only and "main1" in self.conns and Conn == self.conns["main1"]:
			key = "main1"

		# get the id/key that corresponds in self.conns
		elif Conn in self.conns.values():
			key = next(key for key, value in self.conns.items() if value == Conn)

			if key != Conn.key_id:
				self.__class__._log.warning("Connection key_id not the same as first value's key in self.conns, multiple same values in self.conns")

		# Conn does not match ConnectionHandler' Connections
		else:
			self.__class__._log.error("Conn does not match ConnectionHandler's Connections")

			return False

		self.__class__._log.debug(f"closing and removing Connection '{Conn.key_id}' with open_status '{Conn.open_status}'")

		# attempt to close it
		# if successful remove key from self.conns
		if not Conn.open_status or Conn.close_DB(pragma=pragma):
			if key in self.conns:
				self.conns.pop(key)

			return True

		else:
			return False


	def get_conn(self, read_only:bool=True, 
						journal_mode:str="", 
						init_DB: Union[Callable, None]=None, 
						persist:bool=False) -> Connection:

		re_conn = None

		if not read_only:
			# check for main Connection
			if not "main1" in self.conns:
				self.__class__._log.error("no 'main1' Connection in ConnectionHandler")

				return

			# check if main Connection is connected
			elif not self.conns["main1"].open_status:
				if self.conns["main1"].open_DB(read_only) is not None:
					re_conn = self.conns["main1"]

				else:
					pre = hash(">{}< get_conn failed opening 'main1' Conn")
					self.__class__._log.error(pre)

					raise Exception(pre)

			elif self.conns["main1"].open_status:
				# main conn already opened

				# check if this is the same thread that created "main" conn
				# return the main conn if so
				if self.conns["main1"].thread_id == get_ident():
					re_conn = self.conns["main1"]

				# if we have journal_mode we can differentiate further
				# if not, we need to know if DB is set to journal_mode WAL
				elif len(journal_mode) > 0 and journal_mode.upper() == "WAL":
					re_conn = self._add_conn(read_only=False, persist=persist)

				else:
					pre = hash(">{}< get_conn failed opening additional write Conn")
					self.__class__._log.error(f"{pre}, case journal_mode({journal_mode})")

					raise Exception(pre)

			else:
				self.__class__._log.error("get_conn general condition error")

				return
		
		else:
			# get read_only Connection

			re_conn = self._add_conn(read_only=True, persist=persist)

		# also run init_DB if we have it
		if init_DB is not None:
			init_DB(re_conn)

		return re_conn


	def _get_new_Conn_name(self, ConnType:str) -> str:
		if not ConnType in ("Conn", "main"):
			raise ValueError("ConnType not 'Conn' or 'main'")

		# define n_conn_name
		if any(True for i in self.conns.keys() if ConnType in i):
			n_conn_name = ConnType+str(sorted([int(i[4:]) for i in self.conns.keys() if ConnType in i])[-1]+1)
		
		else:
			n_conn_name = f"{ConnType}1"

		return n_conn_name
