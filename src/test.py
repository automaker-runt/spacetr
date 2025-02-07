import logging, time, os, json
from datetime import timedelta
from string import Template

from fsys.folderinit.folder import Folder
from fsys.io.strf import load
from handler.sql import SqlHand
from hkeep.log import logger
from netw.httpsession import HttpSession
from netw.response import Response
from utils.sql.scheme import Schemers
from utils.strings.format import Formatter, DeFormatter
from utils.dicts import multidicts
from settings import settings


def init_settings():
	global Config

	Config = settings.Config()
	Config.config = settings.Config.load_default_config()

	HttpSession.setConfig(Config)

	
def main():

	start = time.time()

	init_settings()

	log = logging.getLogger()
	logger.init_logger(log, loglvl=20, fileHandlffp=os.path.abspath(Folder.os_projver_folderpath)+'/testlog.log')

	Schemer = Schemers(importerfp='/home/darkminosa/dev/spacetr/src/hkeep/log/sc.test')

	dbf = Folder.os_proj_folderpath+"/"+"test4.sqlite"
	deform = DeFormatter({"0": "v0.1.2"})
	form = Formatter(Template('${id}--${version}--[${time_UTC}] [${loglvl}] ${logger}: $msg'))

	SH = SqlHand(Schemer, dbf, {"log": deform}, ("log", form))

	SH.get_conn(read_only=False)


	#SH.use_formatter(form, "log")

	# SH.ins("_loglvl", ["ERROR"])
	# SH.ins("_logger", ["root"])
	# SH.ins("_msg", ["this is a test message"])
	# SH.ins("_version", ["v0.1.2"])
	# SH.ins("log", [1, '2025-01-15 21:56:15', 1, 1, 1])

	# SH.ins("log", ["[2025-01-23 18:52:35] [INFO ] spacetr.hkeep.log.logger: instantiated root logger 'root'", "[2025-01-23 18:52:35] [ERROR] spacetr.handler.sql: _ins_one failed insert into '_version' version=['v0.1.2', 'v0.1.2']"])
	#SH.ins("log", ["[2025-01-23 18:52:35] [ERROR] me: _ins_one muhaha insert into '_version' version=['v0.1.2', 'v0.1.2']"])


	#re = SH.sel('SELECT time_UTC, version, log.id, loglvl, logger, msg FROM log;')
	#re = SH.sel('SELECT id FROM _loglvl WHERE loglvl="ERROR";')

	Session = HttpSession()

	log.info("this is a test message %(indvarg)s", {"indvarg": "!!!", "_msg_args": ["arg", "value"]})

	print(json.dumps(SH.Scheme.dependancies, indent=4))

	cols = list()
	re = list({v[:v.find('.')] for k, v in SH.Scheme.dependancies.items() if "_msg_args." in k and cols.append(v) is None})

	print(re)
	print(cols)

	re_fk_val = SH.sel(f"SELECT id FROM log WHERE logger_id=?;", (6,), _format=False)

	print(re_fk_val[0][0])

	# for line in re:
	# 	print(line)

	#re = Session.get("https://ipinfo.io", lib="req")
	#re = Response("get", "https://api.spacetraders.io", lib="req")
# 	re = Response("get", "https://httpbin.org/post", lib="hpx", data={
#     "id": 1001,
#     "name": "geek",
#     "passion": "coding",
# })

	# print(re.Response.text)
	# print(re.attempts, re.lib, re.mode)
	# #print(re.Response.http_version)
	# re.Response.headers.pop("date")
	# re.Response.headers.update({"date": ""})
	# print(re.Response.cookies.get_dict())
	# #print(multidicts.make_dict(re.Response.headers))
	# #print(re.Response.headers["date"])

	# time.sleep(5)

	# Session.SessH.close()
	# Session.SessR.close()
	# SH.close()

	# time.sleep(0.2)
	# m = timedelta(seconds=time.time()-start)
	# print(m)


if __name__ == "__main__":
	main()

