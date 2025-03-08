# rename
import os

from hkeep.error import tb
from hkeep.log.logger import get_logger


def file(fp:str, new_fp:str) -> bool:
	
	_log = get_logger(__name__)
	
	if not os.path.exists(fp):
		_log.error(f"file {fp[fp.rfind('/')+1:]} does not exist and failed to be renamed")

		return False

	try:
		os.rename(fp, new_fp)

	except Exception as E:
			_log.error(tb(E))

			return False

	else:
		return True
