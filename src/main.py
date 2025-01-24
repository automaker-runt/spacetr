
# main

import __main__

import time, queue, sys, os
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

	# create QueueHandler
	queHandler = logging.handlers.QueueHandler(q)

	# add Queue to logger as another Handler
	logger.setHandler(logger=log,
					handler=queHandler,
					formatter=formatter)

	# init logger with FileHandler
	logger.init_logger(log, formatter=formatter, loglvl=20)

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

	for q in qs[-1::-1]:
		q.put(Config.config["ExitThreadSignal"])
		time.sleep(0.1)


def thr_sql_log(Sql_h:SqlHand, ev_quit:threading.Event, q:queue.Queue):
	global Config

	# initiating DB-conn and Scheme in Sql_h
	Sql_h.open_db()

	last_cycle = False
	# dequeueing from logger QueueHandler and saving into DB
	while not last_cycle or (last_cycle and not q.empty()):
		msg = q.get()
		# check for str type and exit signal
		if isinstance(msg, str) and msg == Config.config["ExitThreadSignal"]:
			last_cycle = True
			log.info("closing DB connection")

		# log it normally if it is LogRecord
		elif isinstance(msg, logging.LogRecord):
			Sql_h.ins('log', msg.getMessage())

			if last_cycle and q.empty():
				break

	Sql_h.conn = Sql_h.close_db(Sql_h.conn)


def main():

	# TODO
	# -redo request and response classes
	# -create second SQLHandler for network traffic that integrates with request and response
	# -port over new version of File class, for seemless file ollover when certain size or time
	###

	sQ = queue.SimpleQueue()
	init_logger(sQ)

	init_settings()

	events = list()
	wake_up_qs = [sQ]
	threads = list()

	Schemer = Scheme(importerfp='utils/sql/scheme.ex')
	Deform = DeFormatter({"0": __version__})
	Form = Formatter(Template('${id}--${version}--[${time_UTC}] [${loglvl}] ${logger}: $msg'))
	dbf = '/home/darkminosa/dev/test.sqlite'

	SH = SqlHand(Schemer, dbf, {"log": Deform}, ("log", Form))

	ev_t_sql_log_end = threading.Event()
	events.append(ev_t_sql_log_end)
	t_sql_log = threading.Thread(target=thr_sql_log, args=(SH, ev_t_sql_log_end, sQ), name="t_sql_log", daemon=True)
	threads.append(t_sql_log)
	t_sql_log.start()

	while True:
		inp = input("q for shutdown: ")
		if inp.lower() == "q":
			break

	shutdown(events, wake_up_qs)

	for thr in threads:
		to = None if thr.name != "t_sql_log" else 2.31
		thr.join(to)

		if thr.is_alive():
			log.warning(f"thread '{thr.name}' didn't auto-close on shutdown call")


if __name__ == "__main__":

	main()

	# print(sQ.get().getMessage())