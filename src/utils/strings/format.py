# format
from string import Template
from typing import Union

from hkeep.error import tb
from hkeep.log.logger import get_logger


class Formatter:

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
