# history
from collections.abc import Iterable
from typing import Union


class MenuOptions:

	def __init__(self, values:dict):
		self.values = values


	def __str__(self) -> str:
		# s = str()

		# for k in self.values:
		# 	s += f'{k}: {self.values[k]}\n'

		# return s
		return str(self.values)


	def _set(self, inp: Union[Iterable]) -> None:
		if isinstance(inp, Iterable) and not isinstance(inp, dict):
			for item in inp:
				self.values.update({item[0]: item[1]})
		elif isinstance(inp, dict):
			for k in inp:
				self.values.update({k: inp[k]})
		elif isinstance(inp, MenuOptions):
			self.values.update(inp.values)
