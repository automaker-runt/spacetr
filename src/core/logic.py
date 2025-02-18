# logic

import time, queue
import threading

from core.ships import Ship
from hkeep.error import tb
from hkeep.log.logger import get_logger
from netw.httpsession import HttpSession
from settings.settings import Config
from utils.strings.shorten import short


def core_start(NetwSession:HttpSession,
				events:list,
				threads:list,
				Config:Config):
	# starts core game procedures

	_log = get_logger(__name__)
	ShipH = None
