
# main

import __main__

import time, queue, threading
import logging, logging.handlers

from fsys import *
from hkeep import *
from netw import *
from utils import *
from settings import *


# instantiate version keeper, include in log startup
# need possibility to track version through logging messages
# need to have pipeline for logging Handler to directly go to SQL and INSERT


def init_logger(q:queue.Queue):
	# instantiate parent logger
	global log
	log = logging.getLogger("spacetr")

	# make own milisecond datetime format by ommitting datefmt parameter
	formatter = logging.Formatter('[{asctime}] [{levelname:<5}] {name}: {message}', style='{')
	logging.Formatter.converter = time.gmtime

	# add Queue to logger as another Handler
	
	logger.setHandler(logger=log,
					handler=logging.handlers.QueueHandler(q),
					formatter=formatter)

	# init logger with FileHandler
	logger.init_logger(log, formatter=formatter)

	print(log.name, log.level, log.handlers)

	log.debug("test start debug msg")
	log.info("test start info msg")


def init_settings():
	global Config

	Config = settings.Config()


def main():

	sQ = queue.SimpleQueue()
	init_logger(sQ)

	while True:
		inp = input("q for continue: ")
		if inp.lower() == "q":
			break

	init_settings()

	print(Config.config)
	log.info("shutting down")


if __name__ == "__main__":

	main()

	# print(sQ.get().getMessage())