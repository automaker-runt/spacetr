# agent
import time
from typing import Union

from core.utils import netw
from core.utils.objmanager import ObjManager
from hkeep.log.logger import get_logger


class Agent:

	_log = get_logger(__name__)


	@classmethod
	def insert(cls, SqlHan, inp:dict) -> bool:
		standard_inp = {
							"created": str(None),
							"name": str(None),
							"credits": str(None),
							"faction": str(None),
							"bearer": str(None),
							"updated": int(time.time()),
		}
		
		if len(inp) == 0 or "name" not in inp:
			cls._log.error(f"insert failed because of no valid inp, len '{len(inp)}'")

			return False

		standard_inp.update(inp)

		if not SqlHan.ins("agents", list(standard_inp.values())):
			cls._log.error(f"insert failed because of no valid inp, len '{len(standard_inp)} and {standard_inp}'")

			return False

		cls._log.info("New competitive Agent '{}' inserted".format(standard_inp["name"]))

		return True


	@classmethod
	def get_agent_id(cls, Objman, inp:str) -> Union[int, None]:
		re = Objman.sel(f"SELECT id FROM agents WHERE name=?;", (inp,), _format=False)

		if len(re) == 0:
			if cls.insert(Objman.Sqhlhan, inp={"name": inp}):
				re = Objman.sel(f"SELECT id FROM agents WHERE name=?;", (inp,), _format=False)
			else:
				cls._log.error(f"get_agent_id failed getting id for agent {inp} due to failed insert")
				return
			
		return re[0][0]


	def __init__(self, Objman:ObjManager, data: Union[dict, None]=None, bearer=None):
		self.Objman = Objman
		self.data = self.api_get_agent() if data is None else data
		self.bearer = bearer
		self.created = int(time.time())


	@property
	def creds(self) -> int:
		return self.data["credits"]

	@property
	def shipCount(self) -> int:
		return self.data["shipCount"]


	def api_get_agent(self) -> Union[dict, None]:
		url = self.Objman.Conf.config["sites"]["SPACETRADERS"]["GET"]["AGENT_INFO"]

		suc, re = self.Objman.get(url=url)

		if not suc:
			self.__class__._log.error("api_get_agent failed to get agent")
			return

		else:
			re_dec = re.Response.json()

			return re_dec["data"]


	def insert_(self) -> bool:
		standard_inp = {
							"created": self.created,
							"name": self.data["symbol"],
							"credits": self.data["credits"],
							"faction": self.data["startingFaction"],
							"bearer": self.bearer,
							"updated": int(time.time()),
		}
		
		if len(inp) == 0 or not any(i in inp for i in standard_inp.keys()):
			cls._log.error(f"insert failed because of no valid inp, len '{len(inp)}'")

			return False

		standard_inp.update(inp)

		if not self.Objman.ins("agents", list(standard_inp.values())):
			cls._log.error(f"insert failed with values '{list(standard_inp.values())}'")

			return False

		cls._log.info("New competitive Agent '{}' inserted".format(standard_inp["name"]))

		return True

