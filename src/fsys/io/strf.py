# strf

import logging, os, time
from hkeep.error import tb
from hkeep.logger import get_logger


def save(stringy:str, fp:str, attempt:int=0, max_tries:int=5, active_log=True) -> bool:

	_log = get_logger(__name__)

	try:	
		with open(fp, "w") as f1:
			f1.write(stringy)

	except Exception as E:
		attempt += 1
		if attempt >= max_tries:
			if active_log:
				_log.error(f"not able to save into {fp}; {tb(E)}")

			if attempt < max_tries+1:
				alternate_fp = fp[:fp.rfind("/")]+"/"+"altfile_"+str(int(time.time()))+".save"
				if active_log:
					_log.info(f"saving into {alternate_fp}")

				time.sleep(3)

				return save(stringy, alternate_fp, attempt=attempt+1, active_log=active_log)

			return False

		else:
			if active_log:
				_log.warning(f"not able to save into {fp}; {tb(E)}")

			time.sleep(1)

			return save(stringy, fp, attempt=attempt+1, active_log=active_log)

	else:
		return True