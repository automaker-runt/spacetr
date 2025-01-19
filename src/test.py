import logging, time, os
from string import Template

from fsys.folderinit.folder import Folder
from fsys.io.strf import load
from handler.sql import SqlHand
from hkeep.log import logger
from utils.sql.scheme import Scheme
from utils.strings.format import Formatter


log = logging.getLogger()
logger.init_logger(log, loglvl=20, fileHandlffp=os.path.abspath(Folder.os_proj_folderpath)+'/testlog.log')

Schemer = Scheme(importerfp='utils/sql/scheme.ex')

dbf = '/home/darkminosa/dev/test.sqlite'

SH = SqlHand(Schemer, dbf)

form = Formatter(Template('${id}--${version}--[${time_UTC}] [${loglvl}] ${logger}: $msg'))

SH.use_formatter(form)

re = SH.sel('SELECT time_UTC, log.id, loglvl, logger, msg FROM log;')

print(re)

while True:
	time.sleep(3)

SH.close_db(SH.conn)