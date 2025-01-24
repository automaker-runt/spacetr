# schema

from hkeep.error import tb
from hkeep.log.logger import get_logger


class Schema:

	_log = get_logger(__name__)
	
	def __init__(self, inp:str) -> None:
		try:
			if not isinstance(inp, str):
				raise Exception('inp provided to Schema() is not a str')

			self.raw_schema = inp
			self.columns = list()
			self.schema = self.conv_schema(inp)
			self.table = self.schema[0].split()[-1][:-1]

		except Exception as E:
			self.__class__._log.error(tb(E))


	def conv_schema(self, inp:str) -> list:

		# taking multiline str with sql create table comm
		# making a list with every new line an item

		outp = list()

		for line in inp.split('\n'):
			first = line.split()[0]

			if not first.lower() in ('create', 'foreign') and not ',' in first and not ')' in first:
			#if all([not first.lower() in {'create', 'foreign'}, not any([',' in first, ')' in first])]):
				self.columns.append(first)

			outp.append(line.strip())

		return outp
