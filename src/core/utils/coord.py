# coord
import math
from typing import Union


class GameCoord:

	def __init__(self, x: Union[int, str], y: Union[int, str], wp:str):
		# transform str coordinates to prorietary coordinate
		self.coord = (int(x), int(y))
		self.wp = wp
		self.sys = wp[:wp.rfind('-')]


	@property
	def coords(self):
		return f"{self.coord[0]}::{self.coord[1]}"

	def __str__(self) -> str:

		return f"{self.wp}_{self.coord[0]}::{self.coord[1]}"


def distance(wp1:GameCoord, wp2:GameCoord) -> float:
	# from doc https://github.com/SpaceTradersAPI/api-docs/wiki/Travel-Fuel-and-Time
	pre_sqrr = ((wp1.coord[0]-wp2.coord[0])**2)+((wp1.coord[1]-wp2.coord[1])**2)

	return round(math.sqrt(pre_sqrr), 3)


if __name__ == "__main__":
	c1 = GameCoord(19, 183, "Tx-T32-TT")
	c2 = GameCoord(-41, 7, "Tx-T32-TTT")

	re = str(distance(c2, c1))

	print(re)
	print(c2)