# marketdata
import time, copy
import pandas as pd
from typing import Union

from core.agent import Agent
from core.utils.objmanager import ObjManager
from core.waypoints import Waypoint
from hkeep.log.logger import get_logger
from utils.dicts import create 
from utils.sql import strings
from utils.time import ISO_to_epoch


class Market:

	_log = get_logger(__name__)
	warned_no_DB_trades = False

	@classmethod
	def get_marketdata(cls, Objman:ObjManager) -> pd.core.frame.DataFrame:
		# can only get it from DB
		# TODO rewrite it for DISTINCT wp_symbol, side, good
		com = "SELECT * FROM market_avail_view;"

		re = Objman.sel(com, _format=False)

		cols = ["id", "waypoint", "coords", "side", "good", "quantity", "price", "maker", "discovery", "updated"]

		if len(re) == 0:
			cls._log.warning("no marketdata found in DB")

			return pd.DataFrame(columns=cols)

		return pd.DataFrame(re, columns=cols)


	@classmethod
	def get_trades(cls, Objman:ObjManager) -> pd.core.frame.DataFrame:
		# can only get it from DB
		com = "SELECT * FROM trades_view;"

		re = Objman.sel(com, _format=False)

		cols = ["id", "trade_time", "waypoint", "side", "good", "quantity", "price", "volume", "taker", "maker", "net_profit", "updated"]

		if len(re) == 0:
			if not cls.warned_no_DB_trades:
				cls.warned_no_DB_trades = True
				cls._log.warning("no trade history found in DB")
			else:
				cls._log.debug("no trade history found in DB")

			return pd.DataFrame(columns=cols)

		return pd.DataFrame(re, columns=cols)


	def __init__(self, Objman:ObjManager):
		self.Objman = Objman
		self.df = self.__class__.get_marketdata(self.Objman)
		self.hdf = self.__class__.get_trades(self.Objman)


	def new_mkt_entries(self, inp:list, wp:str, inp_type:str="good") -> bool:
		# list full of dicts
		maker_id = Agent.get_agent_id(self.Objman, "NPC")
		wp_id = Waypoint.get_wp_id(self.Objman, wp)
		
		for good in inp:
			if inp_type == "good":	
				entry = {
							"waypoints_id": wp_id,
							"side": 0 if good["type"]=="IMPORT" else 1,
							"goods": good["symbol"],
							"quantity": good["tradeVolume"],
							"price": good["sellPrice"] if good["type"]=="IMPORT" else good["purchasePrice"],
							"maker_id": maker_id
				}

			elif inp_type == "ship":
				entry = {
							"waypoints_id": wp_id,
							"side": 1,
							"goods": good["type"],
							"quantity": 1,
							"price": good["purchasePrice"],
							"maker_id": maker_id
				}

			else:
				self.__class__._log.error(f"new_mkt_entries has been called with wrong inp_type '{inp_type}'")
				return False

			where, sel_dict = create.dict_sql_sel(list(entry.keys()), list(entry.values()))
			com = f"SELECT market.id,{strings.get_str_sql_sel_cols(entry)} FROM market WHERE {where};"
			com_vals = tuple(sel_dict.values())

			re = self.Objman.sel(com, com_vals, _format=False)

			# if one entry already in there
			if len(re) == 1:
				# needs the id of goods from _goods to replace goods in entry with goods_id
				re_uniq = self.Objman.sel("SELECT id FROM _goods WHERE goods=?", (entry["goods"],), _format=False)
				uniq_dict = sel_dict.copy()
				uniq_dict.pop("goods")
				uniq_dict.update({"goods_id": re_uniq[0][0]})

				# update the updated column
				if not self.Objman.updt(table="market", cols=["updated"], vals=[int(time.time())], unique=uniq_dict):
					self.__class__._log.error(f"new_mkt_entries failed updating entry with id '{re[0][0]}'")

				self.__class__._log.debug(f"updated market entry at {wp} for {'SELL' if re[0][2]==1 else 'BUY'} {re[0][4]} {re[0][3]} @{re[0][5]}c")

			# if no entry
			elif len(re) == 0:
				# insert the entry
				disc = int(time.time())
				entry.update({
								"discovery": disc,
								"updated": disc
					})
				if not self.Objman.ins("market", list(entry.values())):
					self.__class__._log.error(f"new_mkt_entries failed inserting entry '{list(entry.values())}'")

				self.__class__._log.info("new market entry at {} for {} {} {} @{}c".format(str(Waypoint.get_wp_GameCoord(self.Objman, wp)),
																							'SELL' if entry["side"]==1 else 'BUY',
																							entry["quantity"],
																							entry["goods"],
																							entry["price"]))

			else:
				self.__class__._log.error(f"new_mkt_entries returned multiple identical entries with ids: '{list(i[0] for i in re)}'")

				return False

		# update self.df
		self.df = self.__class__.get_marketdata(self.Objman)

		return True


	def new_trd_entries(self, inp:list, wp:str) -> bool:
		# list full of dicts
		maker_id = Agent.get_agent_id(self.Objman, "NPC")
		wp_id = Waypoint.get_wp_id(self.Objman, wp)
		
		for trade in inp:
			entry = {
						"trade_time": ISO_to_epoch(trade["timestamp"]),
						"waypoints_id": Waypoint.get_wp_id(self.Objman, trade["waypointSymbol"]),
						"side": 0 if trade["type"]=="PURCHASE" else 1,
						"goods": trade["tradeSymbol"],
						"quantity": trade["units"],
						"price": trade["pricePerUnit"],
						"volume": trade["totalPrice"],
						"taker_id": Agent.get_agent_id(self.Objman, trade["shipSymbol"][:trade["shipSymbol"].rfind('-')]), # get id or add it to agents
						"maker_id": maker_id,
						"net_profit": None
			}

			# because net_profit cases of None, SELECT will fail
			# need to remove it from the dict
			sel_dict = copy.deepcopy(entry)
			sel_dict.pop("net_profit")
			where, sel_dict = create.dict_sql_sel(list(sel_dict.keys()), list(sel_dict.values()))
			com = f"SELECT trades.id,{strings.get_str_sql_sel_cols(entry)} FROM trades WHERE {where};"
			com_vals = tuple(sel_dict.values())

			re = self.Objman.sel(com, com_vals, _format=False)

			if len(re) == 0:
				# insert the entry
				entry.update({"updated": int(time.time())})
				if not self.Objman.ins("trades", list(entry.values())):
					self.__class__._log.error(f"new_trd_entries failed inserting entry '{list(entry.values())}'")

				self.__class__._log.debug("new trade entry at {} for {} {} {}".format(str(Waypoint.get_wp_GameCoord(self.Objman, wp)), trade["type"], entry["quantity"], entry["goods"]))

			elif len(re) > 1:
				self.__class__._log.error(f"new_trd_entries returned multiple identical entries with ids: '{list(i[0] for i in re)}'")

				return False

		# update trades
		self.hdf = self.__class__.get_trades(self.Objman)

		return True
