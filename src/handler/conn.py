import time
import sqlite3
from collections.abc import Callable
from threading import get_ident
from typing import Union

from hkeep.log.logger import get_logger
from utils.snapq import SnapshotQueue
from utils.sql.conn import Connection
from utils.strings.xxhash import getHash


class ConnectionHandler:

	_log = get_logger(__name__)


	def __init__(self, dbfp:str):
		self.conns = dict()
		self.dbfp = dbfp
		self.block_add = False
		self.block_add_q = SnapshotQueue()


	def _add_conn(self, read_only:bool=False, open_conn:bool=True, persist:bool=True) -> Union[Connection, None]:
		
		# implement block
		own_ident = None
		if self.block_add or not self.block_add_q.empty():
			own_ident = getHash(str(get_ident()))
			self.block_add_q.put(own_ident)
			
			while self.block_add_q.snapshot()[0] != own_ident:
				time.sleep(0.005)

		self.block_add = True

		# starting name is either main1 or Conn1
		n_conn_name = self._get_new_Conn_name("Conn" if read_only else "main")

		if n_conn_name in self.conns:
			self.__class__._log.warning("{} already in conns: {}".format(n_conn_name, list(self.conns.keys())))

		Conn = Connection(self.dbfp, read_only=read_only, open_conn=open_conn, persist=persist, key_id=n_conn_name)
		
		self.conns.update({n_conn_name: Conn})

		self.block_add = False
		if own_ident and not self.block_add_q.empty():
			self.block_add_q.get()

		return Conn


	def remove_conn(self, Conn:Connection, pragma:str='', force:bool=False) -> bool:
		# type check Conn
		if not isinstance(Conn, Connection):
			self.__class__._log.error(f"remove_conn called with wrong Conn type: {type(Conn)}")

			return False

		if Conn.key_id in self.conns and self.conns[Conn.key_id].thread_id == get_ident():
			key = Conn.key_id

		elif Conn in self.conns.values():
			self.__class__._log.error("remove_conn initiated by thread %(threadID)s without it being the opener, Conn threadID:{} read_only:{} persist:{}".format(Conn.thread_id,
																																								Conn.read_only,
																																								Conn.persist),
																		{"threadID": get_ident(), "_msg_args": ["arg", "value"]})

			return False

		else:
			self.__class__._log.error("remove_conn initiated by thread %(threadID)s but Conn Obj not in conns.values(), Conn threadID:{} read_only:{} persist:{}".format(Conn.thread_id,
																																										Conn.read_only,
																																										Conn.persist),
																		{"threadID": get_ident(), "_msg_args": ["arg", "value"]})

			return False

		self.__class__._log.debug(f"closing and removing Connection '{Conn.key_id}' with open_status '{Conn.open_status}'")

		# attempt to close it
		# if successful remove key from self.conns
		if not Conn.open_status or Conn.close_DB(pragma=pragma, force=force):
			if key in self.conns:
				self.conns.pop(key)

			return True

		else:
			return False


	def remove_thr_conns(self, pragma:str='') -> bool:
		# lookup all Conns
		remove_conns = list()
		results = list()

		for Conn in self.conns:
			if self.conns[Conn].thread_id == get_ident():
				remove_conns.append(Conn)

		for Conn in remove_conns:
			results.append(self.remove_conn(self.conns[Conn], pragma, force=True))

		if len(results) == 0:
			results.append(True)
		
		return all(results)


	def get_conn(self, read_only:bool=True, 
						journal_mode:str="", 
						init_DB: Union[Callable, None]=None, 
						persist:bool=False) -> Connection:

		re_conn = None

		if not read_only:
			# check for main Connection
			if "main1" not in self.conns:
				self._add_conn(open_conn=True, persist=True)
				re_conn = self.conns["main1"]

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
		if init_DB is not None and not read_only and persist:
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
