
# main

import __main__

import time, queue
import threading
import logging, logging.handlers
from string import Template

from handler.sql import SqlHand
from hkeep.log import logger
from settings import settings
from utils.sql.scheme import Scheme
from utils.strings.format import Formatter, DeFormatter
from version import __version__


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


def shutdown(ev:set, qs:set):
	for e in ev:
		e.set()

	log.info("shutting down")
	Config.save()

	for q in qs:
		q.put("shutdown")


def thr_sql_log(Sql_h:SqlHand, ev_quit:threading.Event, q:queue.Queue):
	# initiating DB-conn and Scheme in Sql_h
	Sql_h.open_db()

	# dequeueing from logger QueueHandler and saving into DB
	while not ev_quit.is_set():
		Sql_h.ins('log', q.get().getMessage())

	Sql_h.close_db(Sql_h.conn)


def main():

	sQ = queue.SimpleQueue()
	init_logger(sQ)

	init_settings()

	events = list()
	wake_up_qs = [sQ]

	Schemer = Scheme(importerfp='utils/sql/scheme.ex')
	Deform = DeFormatter({"0": __version__})
	Form = Formatter(Template('${id}--${version}--[${time_UTC}] [${loglvl}] ${logger}: $msg'))
	dbf = '/home/darkminosa/dev/test.sqlite'

	SH = SqlHand(Schemer, dbf, {"log": Deform}, ("log", Form))

	ev_t_sql_log_end = threading.Event()
	events.append(ev_t_sql_log_end)
	t_sql_log = threading.Thread(target=thr_sql_log, args=(SH, ev_t_sql_log_end, sQ), name="t_sql_log", daemon=True)
	t_sql_log.start()

	while True:
		inp = input("q for shutdown: ")
		if inp.lower() == "q":
			break

	shutdown(events, wake_up_qs)

	# while not sQ.empty():
	# 	rec = sQ.get()
	# 	print(f"{rec._version+' ' if hasattr(rec, "_version") else 'no attr '}{rec.getMessage()}")


if __name__ == "__main__":

	main()

	# print(sQ.get().getMessage())