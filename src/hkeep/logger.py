# logger

import logging, os, time
from typing import Union
from fsys.folderinit.folder import Folder
from hkeep.error import tb


def get_logger(name:str) -> logging.Logger:
	_logger = logging.getLogger("spacetr."+name)

	# setLvl(_logger)
	# setHandler(_logger,
	# 			handler=logging.FileHandler(filename=f'{os.path.abspath(Folder.os_proj_folderpath)}/log_UTC.txt', encoding='utf-8', mode='a'),
	# 			formatter=logging.Formatter('[{asctime}] [{levelname:<5}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{')
	# 	)

	return _logger


def setLvl(obj:Union[logging.Logger, logging.Handler], level:int=20) -> bool:
	# NOTSET 0
	# DEBUG 10
	# INFO 20
	# WARNING 30
	# ERROR 40
	# CRITICAL 50

	_log = get_logger(__name__)
	
	try:
		obj.setLevel(level)

	except Exception as E:
		_log.error(tb(E))

		return False

	else:
		ad = str()
		if isinstance(obj, logging.Logger):
			ad = f" to logger '{obj.name}'"
		elif isinstance(obj, logging.Handler):
			ad = f" to handler {obj}"
		else:
			ad = f" to {type(obj)}"

		_log.info(f"set new logLevel {level}{ad}")

		return True


def setHandler(logger:logging.Logger,
				handler:logging.Handler,
				formatter:logging.Formatter,
				) -> bool:
		
	_log = get_logger(__name__)

	try:
		handler.setFormatter(formatter)
		logger.addHandler(handler)

	except Exception as E:
		_log.error(tb(E))
		return False

	else:
		_log.info(f"set new handler of type '{type(handler)}' to logger '{logger.name}'")
		return True


def get_Format() -> logging.Formatter:
	dt_fmt = '%Y-%m-%d %H:%M:%S'
	formatter = logging.Formatter('[{asctime}] [{levelname:<5}] {name}: {message}', dt_fmt, style='{')
	logging.Formatter.converter = time.gmtime

	return formatter


def init_logger(logger:logging.Logger, formatter: Union[logging.Formatter, None]=None) -> None:
	# build formatter
	if formatter is None or not isinstance(formatter, logging.Formatter):
		formatter = get_Format()

	# build handler and set formatter, logging level to it, then add the handler to logger
	main_log_handler = logging.FileHandler(filename=f'{os.path.abspath(Folder.os_proj_folderpath)}/log_UTC.txt', encoding='utf-8', mode='a')
	main_log_handler.setFormatter(formatter)
	logger.setLevel(logging.INFO)
	logger.addHandler(main_log_handler)

	# get own logger to log action
	_log = get_logger(__name__)

	if logger.name in ("", "root"):
		_log.info(f"instantiated root logger '{logger.name}'")
	elif "." in logger.name:
		_log.info(f"instantiated logger '{logger.name}'")
	else:
		_log.info(f"instantiated parent logger '{logger.name}'")


class VersionFilter(logging.Filter):
	'''
	class manipulates every LogRecord with additional attribute
	_version to contain current main version, if set through
	classmethod set_version()
	'''

	_version = "unset"


	@classmethod
	def set_version(cls, ver:str) -> None:
		cls._version = ver


	def filter(self, record:logging.LogRecord):
		record._version = self.__class__._version

		return True