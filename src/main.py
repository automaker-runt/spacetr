
# main

import __main__

import time, queue
import threading
import logging, logging.handlers

from version import __version__
from fsys import *
from handlers import *
from hkeep import *
from netw import *
from settings import *
from utils import *


# need to have pipeline for logging Handler to directly go to SQL and INSERT


def init_logger(q:queue.Queue):
	# instantiate parent logger
	global log
	log = logging.getLogger("spacetr")

	# make own milisecond datetime format by ommitting datefmt parameter
	formatter = logging.Formatter('[{asctime}] [{levelname:<5}] {name}: {message}', style='{')
	logging.Formatter.converter = time.gmtime

	# init logger with FileHandler
	logger.init_logger(log, formatter=formatter, loglvl=20)

	# create VersionFilter and set version
	logger.VersionFilter.set_version(__version__)
	verFilter = logger.VersionFilter()

	# create QueueHandler and add verFilter to it
	queHandler = logging.handlers.QueueHandler(q)
	queHandler.addFilter(verFilter)

	# add Queue to logger as another Handler
	logger.setHandler(logger=log,
					handler=queHandler,
					formatter=formatter)

	log.info(f"started {__version__}")

	log.debug("test start debug msg")
	log.debug(f"{log.name}, {log.level}, {log.handlers}")


def init_settings():
	global Config

	Config = settings.Config()
	Config.config = settings.Config.load_default_config()


def shutdown():
	Config.save()
	log.info("shutting down")


def main():

	sQ = queue.SimpleQueue()
	init_logger(sQ)

	while True:
		inp = input("q for continue: ")
		if inp.lower() == "q":
			break

	init_settings()

	print(Config.config)

	shutdown()

	while not sQ.empty():
		rec = sQ.get()
		print(f"{rec._version+' ' if hasattr(rec, "_version") else 'no attr '}{rec.getMessage()}")


if __name__ == "__main__":

	main()

	# print(sQ.get().getMessage())