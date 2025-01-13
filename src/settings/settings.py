# settings

import os
from fsys.folderinit.folder import Folder
from fsys.io import jsonf
from fsys import create
from hkeep.logger import get_logger


class Config:


	def __init__(self):
		self.config = self.load()


	def load(self) -> dict:

		_log = get_logger(__name__)

		if not "config.json" in Folder.get_folder_content(os.path.abspath(Folder.os_proj_folderpath)):
			# create config.json
			# then load default config and save it

			if create.file(f"{os.path.abspath(Folder.os_proj_folderpath)}/config.json"):
				_log.info(f"Created 'config.json' in {os.path.abspath(Folder.os_proj_folderpath)}")

			else:
				_log.error(f"Couldn't create 'config.json' in {os.path.abspath(Folder.os_proj_folderpath)}")


		if os.stat(f"{os.path.abspath(Folder.os_proj_folderpath)}/config.json").st_size >= 9:
			re, settings = jsonf.load(f"{os.path.abspath(Folder.os_proj_folderpath)}/config.json")

			_log.info(f"loaded settings from {settings["path_config"]}")

			assert re, "not loading config"

		else:
			# load default_config
			settings = self.load_default_config()

			_log.info(f"loaded default settings")

			# save default_config
			assert jsonf.save(settings, settings["path_config"]), "not saving config"

		return settings


	def save(self) -> bool:

		_log = get_logger(__name__)

		# save config
		assert jsonf.save(self.config, self.config["path_config"]), "not saving config"
		_log.info(f"saved settings to {self.config["path_config"]}")

		return True


	def update(self, it: Union[dict, list, tuple]) -> None:

		self.config.update(it)


	def load_default_config(self) -> dict:
		settings = {
						"path_config": f"{os.path.abspath(Folder.os_proj_folderpath)}/config.json"
		}

		return settings
