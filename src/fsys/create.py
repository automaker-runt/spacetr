# create
import os

from hkeep.error import tb
from hkeep.log.logger import get_logger


def file(fp:str) -> bool:

	_log = get_logger(__name__)

	if os.path.exists(fp):
		_log.info(f"file {fp[fp.rfind('/')+1:]} already exists in {fp[:fp.rfind('/')]}")

		return True

	else:

		try:
			f1 = open(fp, "a")

		except Exception as E:
			_log.error(tb(E))

			return False

		else:
			f1.close()
			# TODO make the path folder divider OS independant with settings
			_log.info(f"created file {fp[fp.rfind('/')+1:]} in {fp[:fp.rfind('/')]}")

			return True
