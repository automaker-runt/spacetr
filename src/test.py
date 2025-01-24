import logging, time, os
from string import Template

from fsys.folderinit.folder import Folder
from fsys.io.strf import load
from handler.sql import SqlHand
from hkeep.log import logger
from utils.sql.scheme import Scheme
from utils.strings.format import Formatter, DeFormatter


log = logging.getLogger()
logger.init_logger(log, loglvl=20, fileHandlffp=os.path.abspath(Folder.os_proj_folderpath)+'/testlog.log')

Schemer = Scheme(importerfp='utils/sql/scheme.ex')

dbf = '/home/darkminosa/dev/test.sqlite'
deform = DeFormatter({"0": "v0.1.2"})
form = Formatter(Template('${id}--${version}--[${time_UTC}] [${loglvl}] ${logger}: $msg'))

SH = SqlHand(Schemer, dbf, {"log": deform}, ("log", form))


#SH.use_formatter(form, "log")

# SH.ins("_loglvl", ["ERROR"])
# SH.ins("_logger", ["root"])
# SH.ins("_msg", ["this is a test message"])
# SH.ins("_version", ["v0.1.2"])
# SH.ins("log", [1, '2025-01-15 21:56:15', 1, 1, 1])

SH.ins("log", ["[2025-01-23 18:52:35] [INFO ] spacetr.hkeep.log.logger: instantiated root logger 'root'", "[2025-01-23 18:52:35] [ERROR] spacetr.handler.sql: _ins_one failed insert into '_version' version=['v0.1.2', 'v0.1.2']"])
#SH.ins("log", ["[2025-01-23 18:52:35] [ERROR] spacetr.handler.sql: _ins_one failed insert into '_version' version=['v0.1.2', 'v0.1.2']"])

re = SH.sel('SELECT time_UTC, version, log.id, loglvl, logger, msg FROM log;')
#re = SH.sel('SELECT id FROM _loglvl WHERE loglvl="ERROR";')

for line in re:
	print(line)

while True:
	time.sleep(3)

SH.close_db(SH.conn)