# tasks
from typing import Union

from core.contracts import Contract
from core.ships import Ship
from core.utils.coord import GameCoord, distance
from core.utils.objmanager import ObjManager
from hkeep.log.logger import get_logger


class PreTask:

	_log = get_logger(__name__)

	existing_pretasks = list()


	def __init__(self, id_:str,
						tsk_item,
						tsk_type:str,
						wps:list):

		'''
		tsk_item: Union[Contract, Trade, Mine, Haul, Nav]
		tsk_type: "contract", "trade", "mine", "haul", "marketdata"
		'''
		self.id_ = id_
		self.tsk_item = tsk_item
		self.tsk_type = tsk_type
		self.wps = wps if None not in wps else None

		self.ship = None
		self.schedule = None

		if self.wps is None:
			self.__class__._log.error(f"'{tsk_type}' PreTask '{id_}' unable to create due to wps including None: {wps}")

		elif self not in self.__class__.existing_pretasks:
			self.__class__.existing_pretasks.append(self)



	# def __init__(self, ttype:str, tdata):
	# 	# ttype, Task type ["trade", "contract", "mining"]
	# 	# tdata, Task data
	# 	self.ttype = ttype
	# 	self.tdata = tdata


class Task:

	_log = get_logger(__name__)


	def __init__(self, Objman:ObjManager,
						PT:PreTask,
						S:Ship):
		
		self.Objman = Objman
		self.PT = PT
		self.S = S
		self.S.has_task = True

		self.hoops = self.calc_hoops()


	def calc_hoops(self):
		# find out the type of PT, take according measures

		if self.PT.tsk_type == "contract":
			# asks for an asteroid / gas giant to mine

			# find out needed good
			goods_needed = [i["tradeSymbol"] for i in self.PT.tsk_item.delivr_goods if i["unitsFulfilled"] < i["unitsRequired"]]

			if len(goods_needed) > 0:
				# we need some type of ore
				if "ORE" in goods_needed[0]:
					# search for optimal waypoint to mine needed good
					com_var = ("ASTEROID", "ENGINEERED_ASTEROID")
					re = self.Objman.sel(f"SELECT id, wp_symbol, wp_type, coords FROM waypoints WHERE wp_type=? OR wp_type=?;", com_var, _format=False)

					if len(re) == 0:
						self.__class__._log.error(f"calc_hoops failed to select {com_var} from waypoints for Task")

					distances = list()
					ship_GC = self.S.coordinates
					lowest_distance = 9999999.0
					
					for entity in re:
						entity_GC = GameCoord(*entity[3].split('::'), entity[1])
						dst = distance(ship_GC, ship_GC)
						distances.append(dst)
						if lowest_distance > dst:
							lowest_distance = dst

					found_wp = None

					for entity, dst in zip(re, distances):
						if dst == lowest_distance:
							found_wp = list(entity).copy()
							found_wp.append(dst)

							break

					if found_wp is None:
						self.__class__._log.error(f"calc_hoops failed to find adequate waypoint to extract for Task")
						return

				else:
					pass
					# TODO: siphoning gas giants taken into calculation
			else:
				# TODO turn contract in
				pass
	