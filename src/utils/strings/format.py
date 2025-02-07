# format
from string import Template
from typing import Union

from hkeep.error import tb
from hkeep.log.logger import get_logger


class Formatter:

	# TODO integrate field width and ljust into the Formatter class intialization, could also use the .format standard to declare a template

	_log = get_logger(__name__)


	def __init__(self, temp:Template) -> None:
		self.templ = temp


	def apply_safe(self, mapp:dict) -> str:

		return self.templ.safe_substitute(mapp)


	def apply(self, mapp:dict) -> Union[str, None]:

		try:	
			s = self.templ.substitute(mapp)

		except Exception as E:
			self.__class__._log.error(f"couldn't substitute with mapping({mapp}), {tb(E)}")

		else:
			return s


class DeFormatter:
	# deformats logging messages into their parts for sql insert

	_log = get_logger(__name__)

	def __init__(self, preset:dict=dict()) -> None:
		self.preset = preset


	def apply(self, inp:list, apl_preset:bool=True) -> list:
		# check for inp type

		if not isinstance(inp, list):
			self.__class__._log.error(f"apply inp is not of list type, rejecting type '{type(inp)}'")

			raise Exception(f"TypeError apply inp is not of list type, rejecting type '{type(inp)}'")

		if len(inp) == 0:
			self.__class__._log.error(f"apply inp is empty list, rejecting '{inp}'")

			raise Exception(f"ValueError apply inp is empty list, rejecting '{inp}'")

		# apply self.preset if apl_preset
		return self.apply_preset(inp) if apl_preset else inp


	def apply_preset(self, inp:list) -> list:
		# need to sort to prevent incresing indexes of inserted presets
		for indx in sorted(list(self.preset.keys())):
			inp.insert(int(indx), self.preset[indx])

		return inp


class DeFormatterLog(DeFormatter):

	def apply(self, inp:str, apl_preset:bool=True) -> list:
		# check for inp type
		start = 22

		if not isinstance(inp, str):
			self.__class__._log.error(f"apply inp is not of str type, rejecting '{inp}'")

			raise Exception(f"TypeError apply inp is not of str type, rejecting '{inp}'")

		if len(inp) == 0:
			self.__class__._log.error(f"apply inp is empty str, rejecting '{inp}'")

			raise Exception(f"ValueError apply inp is empty str, rejecting '{inp}'")

		if len(inp) <= start+1:
			self.__class__._log.error(f"apply inp is too small str, rejecting '{inp}'")

			raise Exception(f"ValueError apply inp is too small str, rejecting '{inp}'")

		# do magic of deformatting

		# first needs to get index of log message from the third ":", which is
		# right after the logger, then we can split first three elements
		third = inp[start:].find(":")+start

		# split first three elements: time_UTC, loglvl, logger
		# also get rid of "[" & "]" & and blank space " " by doing so
		outp = [i.strip().strip("[") for i in inp[:third].split("]") if len(i.strip()) > 0]

		# strip last element msg
		last = [inp[third+1:].strip()]

		# strip splitted logger and msg
		outp.extend(last)

		# apply self.preset if apl_preset
		return self.apply_preset(outp) if apl_preset else outp
