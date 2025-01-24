# settings

import os
from typing import Union
from fsys.folderinit.folder import Folder
from fsys.io import jsonf
from fsys import create
from hkeep.log.logger import get_logger
from utils.strings.shorten import short


class Config:


	def __init__(self):
		self.load()


	def load(self) -> None:

		_log = get_logger(__name__)

		if not "config.json" in Folder.get_folder_content(os.path.abspath(Folder.os_proj_folderpath)):
			# create config.json
			# then load default config and save it

			if create.file(f"{os.path.abspath(Folder.os_proj_folderpath)}/config.json"):
				_log.info(f"Created 'config.json' in {short(os.path.abspath(Folder.os_proj_folderpath))}")

			else:
				_log.error(f"Couldn't create 'config.json' in {os.path.abspath(Folder.os_proj_folderpath)}")


		if os.stat(f"{os.path.abspath(Folder.os_proj_folderpath)}/config.json").st_size >= 9:
			re, settings = jsonf.load(f"{os.path.abspath(Folder.os_proj_folderpath)}/config.json")

			if re:
				_log.info(f"loaded settings from {short(settings["path_config"])}")

			assert re, "not loading config"

		else:
			# load default_config
			settings = self.__class__.load_default_config()

			_log.info(f"loaded default settings")

			# save default_config
			assert jsonf.save(settings, settings["path_config"]), "not saving config"

		self.config = settings


	def save(self) -> bool:

		_log = get_logger(__name__)

		# save config
		if jsonf.save(self.config, self.config["path_config"]):	
			_log.info(f"saved settings to {short(self.config["path_config"])}")

			return True

		else:
			assert False, "not saving config"


	def update(self, iterable: Union[dict, list, tuple]) -> None:

		self.config.update(iterable)


	@classmethod
	def load_default_config(cls) -> dict:
		settings = {
						"DEFAULT_SESSION_HEADERS_LINUX": {
															'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
															'Accept-Encoding': 'gzip, deflate, br, zstd',
															'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
															'Priority': 'u=0, i',
															'Connection': 'keep-alive',
															'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126"',
															'Sec-Ch-Ua-Platform': 'Linux',
															'Sec-Fetch-Dest': 'document',
															'Sec-Fetch-Mode': 'navigate',
															'Sec-Fetch-Site': 'same-origin',
															'Upgrade-Insecure-Requests': '1',
															'User-Agent': 'Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
															},
						"DEFAULT_SESSION_HEADERS_WIN": {
															'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
															'Accept-Encoding': 'gzip, deflate, br',
															'Accept-Language': 'en-US,en;q=0.5',
															'Connection': 'keep-alive',
															'Sec-Fetch-Dest': 'document',
															'Sec-Fetch-Mode': 'navigate',
															'Sec-Fetch-Site': 'same-origin',
															'Upgrade-Insecure-Requests': '1',
															'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
															},
						"path_config": f"{os.path.abspath(Folder.os_proj_folderpath)}/config.json",
						"ExitThreadSignal": "//exit"
		}

		return settings
