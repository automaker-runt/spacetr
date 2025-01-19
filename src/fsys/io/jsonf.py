# jsonf

import json
from typing import Union
from fsys.io import strf
from hkeep.error import tb
from hkeep.log.logger import get_logger


def save(di:dict, fp:str, indent:int=4) -> bool:

	s1 = json.dumps(di, indent=indent)
	_log = get_logger(__name__)

	if strf.save(s1, fp):
		_log.info(f"saved {fp}")

		return True

	else:
		_log = get_logger(__name__)
		_log.error(f"not able to save into {fp}")

		return False


def load(fp:str) -> tuple:

	_log = get_logger(__name__)
	
	try:
		with open(fp,) as f1:
			di = json.load(f1)

	except Exception as E:
		_log.error(f"not able to load data from {fp}; {tb(E)}")

		return (False, {})

	else:
		_log.info(f"loaded data from {fp}")

		return (True, di)
