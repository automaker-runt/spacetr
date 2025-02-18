# history
from collections.abc import Iterable
from typing import Union


class MenuHistory:

	def __init__(self, values:list, mode:str):
		self.values = values
		self.mode = mode


	def add(self, inp: Union[str, Iterable]) -> None:
		if isinstance(inp, str):
			if inp not in self.values:	
				self.values.insert(0, inp)
		elif isinstance(inp, Iterable) and not isinstance(inp, dict):
			self.values = inp.extend([i for i in self.values if i not in inp])
