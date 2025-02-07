# logger

import logging, os, time, sys
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
		#handler.setFormatter(formatter)
		logger.addHandler(handler)

	except Exception as E:
		_log.error(tb(E))
		return False

	else:
		_log.info(f"set new handler of type '{type(handler)}' to logger '{logger.name}'")
		return True


def setNetmsgHandler(logger:logging.Logger,
					handler:logging.Handler
				) -> bool:
		
	def netmsgPassFilter(record:logging.LogRecord) -> bool:
		if record.levelno in [19]:
			return True

		else:
			return False


	_log = get_logger(__name__)
	formatter = logging.Formatter('[{asctime}] [{levelname:<5}] {name}: {message}', style='{')	

	# create blank filter for network traffic
	netmsgFil = logging.Filter()
	# pass own filter method to Fil.filter
	netmsgFil.filter = netmsgPassFilter

	try:
		handler.addFilter(netmsgFil)
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


def init_logger(logger:logging.Logger,
				formatter: Union[logging.Formatter, None]=None,
				loglvl:int=20,
				fileHandlffp:str=None,
				filters:list=list()) -> None:
	
	# build formatter
	if formatter is None or not isinstance(formatter, logging.Formatter):
		formatter = get_Format()

	# build handler and set formatter, logging level to it, then add the handler to logger
	if fileHandlffp is None:	
		main_log_handler = logging.FileHandler(filename=f'{os.path.abspath(Folder.os_projver_folderpath)}/log_UTC2.txt', encoding='utf-8', mode='a')
	else:
		main_log_handler = logging.FileHandler(filename=fileHandlffp, encoding='utf-8', mode='a')

	report_handler = logger.handlers.copy()

	# add filters to main_log_handler
	for fil in filters:	
		main_log_handler.addFilter(fil)

	main_log_handler.setFormatter(formatter)
	logger.setLevel(loglvl)
	logger.addHandler(main_log_handler)

	# there was a handler already added before adding FileHandler
	if len(report_handler) == 1 and loglvl <= 20:
		# create record only for FileHandler
		rec = logging.LogRecord(name="spacetr."+__name__,
								level=20,
								pathname=os.path.dirname(__file__)+"/"+__name__,
								msg=f"logHandler already present {report_handler[0]}",
								lineno=sys._getframe().f_lineno,
								args=tuple(),
								exc_info=tuple())
		main_log_handler.handle(rec)

	# get own logger to log action
	_log = get_logger(__name__)

	if logger.name in ("", "root"):
		_log.info(f"instantiated root logger '{logger.name}'")
	elif "." in logger.name:
		_log.info(f"instantiated logger '{logger.name}'")
	else:
		_log.info(f"instantiated parent logger '{logger.name}'")


def addLoggingLevel(levelName, levelNum, methodName=None):
    # from https://stackoverflow.com/questions/2183233/how-to-add-a-custom-loglevel-to-pythons-logging-facility/35804945#35804945 [20250128]
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `levelName` becomes an attribute of the `logging` module with the value
    `levelNum`. `methodName` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `methodName` is not specified, `levelName.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present 

    Example
    -------
    >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    """
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
       raise AttributeError('{} already defined in logging module'.format(levelName))
    if hasattr(logging, methodName):
       raise AttributeError('{} already defined in logging module'.format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
       raise AttributeError('{} already defined in logger class'.format(methodName))

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)
    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)


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


	def filter(self, record:logging.LogRecord) -> bool:
		record._version = self.__class__._version

		return True