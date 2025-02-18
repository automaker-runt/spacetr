
# main

import __main__

import time, queue, sys, os, json
import threading
import logging

from string import Template
from typing import Union

from fsys.io import jsonf
from handler.sql import SqlHand
from hkeep.error import tb
from hkeep.log import logger
from hkeep.log.qhand import QHand
from netw.httpsession import HttpSession
from netw.request import Request
from settings import settings
from ui import menus, options, history
from utils.sql.scheme import Schemers
from utils.strings.format import Formatter, DeFormatter
from utils.strings.shorten import short
from utils.time import conv_time_time_to_def
from version import __version__


# need to have pipeline for logging Handler to directly go to SQL and INSERT


def init_logger(q:queue.Queue):
	# setup passing filter for loglvl 10, 20, 30, 40, 50
	def GenPassFilter(record:logging.LogRecord) -> bool:
		if record.levelno in [10, 20, 30, 40, 50]:
			return True

		else:
			return False

	
	# instantiate parent logger
	global log
	log = logging.getLogger("spacetr")

	# make own milisecond datetime format by ommitting datefmt parameter
	formatter = logging.Formatter('[{asctime}] [{levelname:<5}] {name}: {message}', style='{')
	logging.Formatter.converter = time.gmtime

	# create QueueHandler
	queHandler = QHand(q)
	
	# create blank filter
	#Fil = logging.Filter()
	# pass own filter method to Fil.filter
	#Fil.filter = GenPassFilter
	# add Fil & netmsgFil to queHandler
	#queHandler.addFilter(Fil)

	# add custom logging level
	#logger.addLoggingLevel("NETMSG", 19)

	# change loglvl of httpx
	#logging.getLogger("httpx").setLevel("NETMSG")

	# add Queue to logger as another Handler
	logger.setHandler(logger=log,
					handler=queHandler,
					formatter=formatter)

	# init logger with FileHandler, loglevel set global
	logger.init_logger(log, formatter=formatter, loglvl=loglevel)#, filters=[Fil])

	log.info(f"started {__version__}")
	#log.netmsg("test network message")

	log.debug("test start debug msg")
	log.debug(f"{log.name}, {log.level}, {log.handlers}")


def init_settings():
	global Config

	Config = settings.Config()
	Config.config = settings.Config.load_default_config()

	HttpSession.setConfig(Config)


def shutdown(ev:set, qs:set):
	for e in ev:
		e.set()

	log.info("shutting down")
	Config.save()

	for q in qs[-1::-1]:
		q.put(Config.config["ExitThreadSignal"])
		time.sleep(0.1)


def thr_sql_log(Sql_h:SqlHand, ev_quit:threading.Event, q:queue.Queue, name:str="t_sql_log"):
	global Config, log

	# initiating DB-conn and Schemers in Sql_h
	if not "main1" in Sql_h.ConnHandler.conns:
		log.error(f"[{name}] exited unsuccessfull, no 'main1' Connection in ConnectionHandler")

		return

	last_cycle = False
	# get Conn here to actually open the DB from this thread
	# and manifest Conn "main1"
	Sql_h.get_conn(read_only=False, persist=True)
	log.info(f"[{name}] instatiated")
		
	try:
		# dequeueing from logger QueueHandler and saving into DB
		while not last_cycle or (last_cycle and not q.empty()):
			LRec = q.get()
			# check for str type and exit signal
			if isinstance(LRec, str) and LRec == Config.config["ExitThreadSignal"]:
				last_cycle = True
				if Sql_h.ConnHandler.conns["main1"].open_status:
					log.info(f"closing DB connection {short(Sql_h.dbfp)}")

			# log it normally if it is LogRecord
			elif isinstance(LRec, logging.LogRecord):
				#print(len(LRec.args), LRec.args)

				# forwarding placeholders in LogRecord.msg to DB
				if isinstance(LRec.args, dict) and len(LRec.args) > 0:	
					Sql_h.ins('log', [conv_time_time_to_def(LRec.created), LRec.levelname, LRec.name, LRec.msg], **LRec.args)

				else:
					Sql_h.ins('log', [conv_time_time_to_def(LRec.created), LRec.levelname, LRec.name, LRec.msg])

				if last_cycle and q.empty():
					break

	except Exception as E:
		log.critical(f"[{name}] failed in while loop, {tb(E)}")

		raise E

	finally:	
		if Sql_h.ConnHandler.conns["main1"].open_status:
			Sql_h.ConnHandler.conns["main1"].close_DB()


def thr_sql_netmsg(netSql_h:SqlHand, ev_quit:threading.Event, q:queue.Queue, name:str="t_sql_netmsg"):
	global Config, log

	# while loop quitter
	quit = False

	# get Conn here to actually open the DB from this thread
	# and manifest Conn "main1"
	netSql_h.get_conn(read_only=False, persist=True)
	log.info(f"[{name}] instatiated")
	
	try:
		# dequeueing from SimpleQueue sQ_netmsg and saving into DB
		while not quit or not q.empty():
			msg = q.get()
			# check for str type and exit signal
			if isinstance(msg, str) and msg == Config.config["ExitThreadSignal"]:
				quit = True
				if netSql_h.ConnHandler.conns["main1"].open_status or len(netSql_h.ConnHandler.conns.keys()) > 1:	
					log.info(f"closing DB connection {short(netSql_h.dbfp)}")

			# log it normally if it is LogRecord, which it isn't
			elif isinstance(msg, list):
				netSql_h.ins('netmsg', msg)

				if quit and q.empty():
					break

	except Exception as E:
		log.critical(f"[{name}] failed in while loop, {tb(E)}")

	finally:
		# need to care about closing 'main1' conn only if it has open_status True
		Request.unset_netmsg()


def main():

	# TODO
	# -why is back not working on selecting url/data?
	# -find out why httpx is not logging requests on INFO lvl
	# -port over new version of File class, for seemless file ollover when certain size or time
	###

	# Q for putting netmsg into DB
	sQ_netmsg = queue.SimpleQueue()
	# Q for logging into DB
	sQ = queue.SimpleQueue()
	init_logger(sQ)

	init_settings()

	events = list()
	wake_up_qs = [sQ, sQ_netmsg]
	threads = list()

	# Setting up Log DB
	#Schemer = Schemers(importerfp='/home/darkminosa/dev/spacetr/src/hkeep/log/scheme.ex')
	Schemer = Schemers(importerfp=Config.config["DB_SCHEME_LOG_FP"])
	Deform = DeFormatter({"0": __version__})
	Form = Formatter(Template('${id}--${version}--[${time_UTC}] [${loglvl}] ${logger}: $msg'))
	dbf = os.path.abspath(Config.config["DB_LOG_FP"])

	SH = SqlHand(Schemer, dbf, {"log": Deform}, ("log", Form))

	# Setting up Spacetraders DB
	SptrSchemer = Schemers(importerfp="../scheme.ex")
	dbf = os.path.abspath("../sptr.sqlite")
	SptrSH = SqlHand(SptrSchemer, dbf)
	SptrSH.get_conn(read_only=False, persist=True)	

	# thread for logging into DB
	ev_t_sql_log_end = threading.Event()
	events.append(ev_t_sql_log_end)
	t_sql_log = threading.Thread(target=thr_sql_log, args=(SH, ev_t_sql_log_end, sQ), name="t_sql_log", daemon=True)
	threads.append(t_sql_log)
	t_sql_log.start()

	# create netmsgSH with Request classmethod
	netmsgSH = Request.set_netmsg(sQ_netmsg, dbfp=Config.config["DB_NETMSG_FP"], scfp=Config.config["DB_SCHEME_NETMSG_FP"])

	# thread for putting network traffic (netmsg) into DB
	ev_t_sql_netmsg_end = threading.Event()
	events.append(ev_t_sql_netmsg_end)
	t_sql_netmsg = threading.Thread(target=thr_sql_netmsg, args=(netmsgSH, ev_t_sql_netmsg_end, sQ_netmsg), name="t_sql_netmsg", daemon=False)
	threads.append(t_sql_netmsg)
	t_sql_netmsg.start()

	NetwSession = HttpSession()
	NetwSession.set_ratelimiter(2)
	NetwSession.set_auth_header(header=BEARER["AGENT"], host="spacetraders.io")
	NetwSession.set_auth_header(header=BEARER["ACCOUNT"], host="https://api.spacetraders.io/v2/register")

	UI_G_History = history.MenuHistory(list(Config.config["sites"]["SPACETRADERS"]["GET"].values()), "get")
	UI_P_History = history.MenuHistory(list(Config.config["sites"]["SPACETRADERS"]["POST"].values()), "post")
	UIOptions = options.MenuOptions({"lib": "req"})

	MainMenu = menus.Menu(NetwSession,
				Config,
				SptrSH,
				get_history=UI_G_History,
				post_history=UI_P_History)
	MainMenu.display()

	
	SptrSH.close()
	shutdown(events, wake_up_qs)

	SH.close()

	for thr in threads:
		to = None if thr.name != "t_sql_log" else 2.31
		thr.join(to)

		if thr.is_alive():
			log.warning(f"thread '{thr.name}' didn't auto-close on shutdown call")


if __name__ == "__main__":

	loglevel = 100 if "log" not in sys.argv else 20
	BEARER = jsonf.load(".env")[1]

	main()
