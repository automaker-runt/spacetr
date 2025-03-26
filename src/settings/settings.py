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

		if not "config.json" in Folder.get_folder_content(os.path.abspath(Folder.os_projver_folderpath)):
			# create config.json
			# then load default config and save it

			if create.file(f"{os.path.abspath(Folder.os_projver_folderpath)}/config.json"):
				_log.info(f"Created 'config.json' in {short(os.path.abspath(Folder.os_projver_folderpath))}")

			else:
				_log.error(f"Couldn't create 'config.json' in {os.path.abspath(Folder.os_projver_folderpath)}")


		if os.stat(f"{os.path.abspath(Folder.os_projver_folderpath)}/config.json").st_size >= 9:
			re, settings = jsonf.load(f"{os.path.abspath(Folder.os_projver_folderpath)}/config.json")

			if re:
				_log.info(f'loaded settings from {short(settings["path_config"])}')

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
			_log.info(f'saved settings to {short(self.config["path_config"])}')

			return True

		else:
			assert False, "not saving config"


	def update(self, iterable: Union[dict, list, tuple]) -> None:

		self.config.update(iterable)


	@classmethod
	def load_default_config(cls) -> dict:
		settings = {
						# "DEFAULT_SESSION_HEADERS_LINUX": {
						# 									'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
						# 									'Accept-Encoding': 'gzip, deflate, br',
						# 									'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
						# 									'Priority': 'u=0, i',
						# 									'Connection': 'keep-alive',
						# 									'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126"',
						# 									'Sec-Ch-Ua-Platform': 'Linux',
						# 									'Sec-Fetch-Dest': 'document',
						# 									'Sec-Fetch-Mode': 'navigate',
						# 									'Sec-Fetch-Site': 'same-origin',
						# 									'Upgrade-Insecure-Requests': '1',
						# 									'User-Agent': 'python-httpx/0.28.1'		# 'python-requests/2.31.0'
						# 									},

						"CALLSIGN_SUFX": ["TRADER", "TR4DER", "TRAD3R", "TR4D3R", "7RADER", "7R4DER", "7RAD3R", "7R4D3R"],

						"path_config": f"{os.path.abspath(Folder.os_projver_folderpath)}/config.json",
						"DB_LOG_FP": f"{os.path.abspath(Folder.os_projver_folderpath)}/test4.sqlite",
						"DB_NETMSG_FP": f"{os.path.abspath(Folder.os_projver_folderpath)}/netmsg.sqlite",
						"DB_SPACETR_FP": f"{os.path.abspath(Folder.os_projver_folderpath)}/sptr.sqlite",
						"DB_LOG_FP_PROD": "/var/local/data/logs_utc.sqlite",
						"DB_NETMSG_FP_PROD": "/var/local/data/netmsg.sqlite",
						"DB_SPACETR_FP_PROD": "/var/local/data/sptr.sqlite",
						#"DB_SPACETR_FP_PROD": f"{os.path.abspath(Folder.os_projver_folderpath)}/sptr.sqlite",
						"DB_SCHEME_LOG_FP": f"{os.path.abspath(Folder.os_projver_folderpath)}/src/hkeep/log/scheme.ex",
						"DB_SCHEME_NETMSG_FP": f"{os.path.abspath(Folder.os_projver_folderpath)}/src/netw/scheme.ex",
						"DB_SCHEME_SPACETR_FP": f"{os.path.abspath(Folder.os_projver_folderpath)}/src/core/scheme.ex",
						
						"DEFAULT_SESSION_HEADERS_LINUX": {'accept': '*/*', 'accept-encoding': 'gzip, deflate, br', 'connection': 'keep-alive'},

															#{'accept': '*/*', 'accept-encoding': 'gzip, deflate, br', 'connection': 'keep-alive'}

						"DEFAULT_SESSION_HEADERS_LINUX_PRIV": {
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
															'User-Agent': 'python requests/httpx'
						},
						"DEFAULT_SESSION_HEADERS_WIN_PRIV": {
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
						"DEFAULT_SESSION_MAX_ATTEMPT_LIB": 2,
						"DEFAULT_SESSION_MAX_ATTEMPT_SESS": 2,
						"ExitThreadSignal": "//exit",
						"FACTIONS": ["QUANTUM", "DOMINION", "ASTRO", "CORSAIRS", "VOID", "OBSIDIAN", "AEGIS", "UNITED", "SOLITARY", "COBALT", "OMEGA", "ECHO", "COSMIC"],
						"FLIGHT_MODE_FRIGATES": "CRUISE",
						"GOOD_TRAIT_MAP": {
								"COPPER_ORE": [
										"COMMON_METAL_DEPOSITS"
								],
								"IRON_ORE": [
										"COMMON_METAL_DEPOSITS"
								],
								"ALUMINUM_ORE": [
										"COMMON_METAL_DEPOSITS"
								]
						},
						"HTTP_REPEAT_INVALIDATION": ("error", "method not allowed", "conflict", "not found"),
						"MARKETDATA_CYCLE": 30,
						"MINIMIZE_NAVIGATION_REQUESTS": False,
						"NAVIGATION_MULTIPLIER": {
													"CRUISE": 25,
													"DRIFT": 250,
													"BURN": 12.5,
													"STEALTH": 30,
						},
						"sites": {
									"SPACETRADERS": {
														"POST": {
																"REGISTER": ["https://api.spacetraders.io/v2/register", {"symbol": "{CALLSIGN}", "faction": "{FactionSymbol}"}],
																"ACCEPT_CONTRACT": "https://api.spacetraders.io/v2/my/contracts/{contractId}/accept",
																"DELIVER_CONTRACT": ["https://api.spacetraders.io/v2/my/contracts/{contractId}/deliver", {"shipSymbol": "{miningShipSymbol}", "tradeSymbol": "{GOOD}", "units": "{QUANTITY}"}],
																"FULLFILL_CONTRACT": "https://api.spacetraders.io/v2/my/contracts/{contractId}/fulfill",
																"GO_ORBIT": "https://api.spacetraders.io/v2/my/ships/{ShipSymbol}/orbit",
																"GO_WAYPOINT": ["https://api.spacetraders.io/v2/my/ships/{ShipSymbol}/navigate", {"waypointSymbol": "{WaypointSymbol}"}],
																"REFUEL": "https://api.spacetraders.io/v2/my/ships/{ShipSymbol}/refuel",
																"REFUEL_AMT": ["https://api.spacetraders.io/v2/my/ships/{ShipSymbol}/refuel", {"units": "{Units}", "fromCargo": "{fromCargo}"}],
																"PURCHASE_SHIP": ["https://api.spacetraders.io/v2/my/ships", {"shipType": "{SHIP_TYPE}", "waypointSymbol": "{shipyardWaypointSymbol}"}],
																"DOCK_SHIP": "https://api.spacetraders.io/v2/my/ships/{ShipSymbol}/dock",
																"EXTRACT_ORES": "https://api.spacetraders.io/v2/my/ships/{miningShipSymbol}/extract",
																"SELL": ["https://api.spacetraders.io/v2/my/ships/{ShipSymbol}/sell", {"symbol": "{GOOD}", "units": "{QUANTITY}"}],
																"JETTISON": ["https://api.spacetraders.io/v2/my/ships/{shipSymbol}/jettison", {"symbol": "{GOOD}", "units": "{QUANTITY}"}],
																"CREATE_SURVEY": "https://api.spacetraders.io/v2/my/ships/{shipSymbol}/survey",
																"USE_SURVEY": ["https://api.spacetraders.io/v2/my/ships/{shipSymbol}/extract/survey", {"signature": "{surveySignature}", "symbol": "{WaypointSymbol}", "deposits": [{"symbol": "{GOOD}"}], "expiration": "{surveyExpiration}", "size": "{SMALL_MODERATE_LARGE}"}],
																"GO_WARP": ["https://api.spacetraders.io/v2/my/ships/{shipSymbol}/warp", {"systemSymbol": "{systemSymbol}"}],
																"GO_JUMP": ["https://api.spacetraders.io/v2/my/ships/{shipSymbol}/jump", {"systemSymbol": "{systemSymbol}"}]
														},
														"GET": {
																"PING": "https://api.spacetraders.io/v2",
																"AGENT_INFO": "https://api.spacetraders.io/v2/my/agent",
																"LOCATION_INFO": "https://api.spacetraders.io/v2/systems/{systemSymbol}/waypoints/{waypointSymbol}",
																"FACTIONS_INFO": "https://api.spacetraders.io/v2/my/factions",
																"CONTRACTS_INFO": "https://api.spacetraders.io/v2/my/contracts",
																"WORLD": "https://api.spacetraders.io/v2/systems",
																"TUTORIAL_ASTEROID" : "https://api.spacetraders.io/v2/systems/{systemSymbol}/waypoints?type=ENGINEERED_ASTEROID",
																"SHIPS_INFO": "https://api.spacetraders.io/v2/my/ships",
																"SHIP_INFO": "https://api.spacetraders.io/v2/my/ships/{ShipSymbol}",
																"FIND_SHIPYARD": "https://api.spacetraders.io/v2/systems/{systemSymbol}/waypoints?traits=SHIPYARD",
																"FIND_MARKETPLACE": "https://api.spacetraders.io/v2/systems/{systemSymbol}/waypoints?traits=MARKETPLACE",
																"SHIP_CARGO": "https://api.spacetraders.io/v2/my/ships/{ShipSymbol}/cargo",
																"WAYPOINTS": "https://api.spacetraders.io/v2/systems/{systemSymbol}/waypoints",
																"MARKETPLACE_DATA": "https://api.spacetraders.io/v2/systems/{systemSymbol}/waypoints/{WaypointSymbol}/market",
																"SHIPYARD_DATA": "https://api.spacetraders.io/v2/systems/{systemSymbol}/waypoints/{WaypointSymbol}/shipyard"
														},
														"PATCH": {
																"FLIGHT_MODE": ["https://api.spacetraders.io/v2/my/ships/{shipSymbol}/nav", {"flightMode": "{CRUISE_BURN_DRIFT_STEALTH}"}]
														}
									}

						},
						"THREAD_ACTF_LOGI_INTERVAL": 1,
						"THREAD_CTRCT_LOGI_INTERVAL": 2,
						"THREAD_CTRCT_LOGI_API_INTERVAL": 1845,
						"THREAD_CORE_JOIN_TIMEOUT": 21.14,
						"THREAD_MAIN_DEFAULT_JOIN_TIMEOUT": 3.31,
						"THREAD_MRKTDF_LOGI_CHECK_WPS_INTERVAL": 600,
						"THREAD_MRKTDF_LOGI_INTERVAL": 2,
						"THREAD_TASK_INTERVAL": 1,
						"THREAD_TASK_JOIN_TIMEOUT": 7.14
		}

		return settings
