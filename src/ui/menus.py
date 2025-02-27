# menus
import json, threading
from python_console_menu import AbstractMenu, MenuItem

from typing import Union

from core.logic import Core
from hkeep.log.logger import get_logger
from ui.history import MenuHistory
from ui.options import MenuOptions
from utils import links
from utils.strings import extract


class OwnAbstractMenu(AbstractMenu):

	_log = get_logger(__name__)

	options = MenuOptions({"post_mode": "json"})

	@classmethod
	def apply_history(cls, hist:MenuHistory) -> str:

		# conti means continues, when set to False, abort
		
		def _fill_keyw(inp:str) -> Union[str, bool]:
			keyw = extract.keyw(inp)
			
			form_di = dict()
			for k in keyw:
				re = input(f"Give value for '{k}', 0 to abort: >")
				if re.isdigit() and re == "0":
					# abort
					return False, None
				else:	
					form_di.update({k: re.strip()})

			inp = inp.format(**form_di)

			return True, inp


		# starts here
		conti = True
		print("Select url")
		if len(hist.values) > 0:	
			print("0. back")
			for k, i in enumerate(hist.values):
				print(f"{k+1}. {i}")
			print("or just input own url")
			re = input("Select Option: >").strip()
			if re.isdigit():
				if int(re) == 0:
					return False, None, None
				
				# case where link also has necessary data field and the value is actually a list
				if hist.mode in ("post", "patch") and isinstance(hist.values[int(re)-1], list):
					link, ndata = hist.values[int(re)-1]

					# need to check data values for needed info
					for k, v in ndata.items():
						if links.needs_format(v):
							print(f"{{{k}: {v}}}")
							conti, f_v =_fill_keyw(v)
								
							if not conti:
								return False, None, None
							else:
								# we don't want to change the values in hist.values, so we first make copy
								ndata = ndata.copy()
								ndata.update({k: f_v})

					# now we can assume we have all needed data for POST
					# we set flag for returning kwargs data key
					data_ready_flag = True

				# no data field necessary, just set link
				else:
					data_ready_flag = False
					link = hist.values[int(re)-1]

				# case where return is only a link that needs formatting
				if links.needs_format(link):
					conti, f_link = _fill_keyw(link)
				else:
					f_link = link

				# case where the link is good unformatted, or has been formatted
				if conti:
					# return according to data_ready_flag	
					if data_ready_flag:	
						return True, f_link, ndata
					else:
						return True, f_link, True
				else:
					return False, None, None

			# case where we input the link
			elif links.is_valid(re):
				if links.needs_format(re):	
					conti, f_link = _fill_keyw(re)

					if conti:
						return True, f_link, True

					else:
						return False, None, None

				else:
					return True, re, None

			else:
				raise ValueError("no valid link input")
		
		else:
			re = input("Input own url: ").strip()
			if len(re) > 0 and links.is_valid(re):
				if links.needs_format(re):	
					conti, f_link = _fill_keyw(re)

					if conti:
						return True, f_link, None

					else:
						return False, None, None

				else:
					return True, re, None
			else:
				raise ValueError("no valid link input")

	@classmethod
	def _set_option(cls, k:str, v: Union[str, int, list, tuple, dict]):
		cls.options._set(((k, v),))


class OptionsHTTPSubMenu(OwnAbstractMenu):
	show_hidden_menu = False

	def __init__(self):
		super().__init__("> spacetr > Options > HTTP\n")

	def initialise(self):
		
		self.add_menu_item(MenuItem(0, "back").set_as_exit_option())
		self.add_menu_item(MenuItem(1, "set lib hpx", lambda: self._set_option("lib", "hpx")).set_as_exit_option())
		self.add_menu_item(MenuItem(2, "set lib req", lambda: self._set_option("lib", "req")).set_as_exit_option())
		self.add_menu_item(MenuItem(3, "set POST data mode json", lambda: self._set_option("post_mode", "json")).set_as_exit_option())
		self.add_menu_item(MenuItem(4, "set POST data mode urlencoded", lambda: self._set_option("post_mode", "data")).set_as_exit_option())

class OptionsSubMenu(OwnAbstractMenu):
	show_hidden_menu = False

	def __init__(self):
		super().__init__("> spacetr > Options\n")

	def initialise(self):
		
		self.add_menu_item(MenuItem(0, "back").set_as_exit_option())
		self.add_menu_item(MenuItem(1, "HTTP", menu=OptionsHTTPSubMenu()))


class Menu(OwnAbstractMenu):
	show_hidden_menu = False
	#options = {}

	# get_history = [i for i in Config.config["sites"]["SPACETRADERS"]["GET"].values()]
	# get_history.append("https://httpbin.org/get")
	# #get_history = get_history.extend(["https://httpbin.org/get"])
	# post_history = [i for i in Config.config["sites"]["SPACETRADERS"]["POST"].values()]
	# #post_history = post_history.extend(["https://httpbin.org/post"])
	data = [{"id": 1001, "name": "geek", "passion": "coding"}, {"symbol": "iMBA_tester", "faction": "COSMIC"}]

	
	@classmethod
	def save_data(cls, inp:dict) -> None:
		if not inp in cls.data and isinstance(inp, dict):
			cls.data.append(inp)

	@classmethod
	def apply_data(cls) -> str:
		print("Select data")
		if len(cls.data) > 0:
			k = int()
			print("0. back")
			for k, i in enumerate(cls.data):
				print(f"{k+1}. {str(i).replace('\n', '')}")
			print("or just input own url")
			re = input("Select Option: >").strip()
			if re.isdigit():
				if int(re) == 0:
					return False, None
				return True, cls.data[int(re)-1]
			else:
				re = json.loads(re)

				return True, re
		else:
			re = json.loads(input("Input own data: ").strip())
			if len(re) > 0:

				return True, re


	def __init__(self, session,
						Conf,
						SqlHan,
						get_history:MenuHistory,
						post_history:MenuHistory,
						BEARER_ACC:dict,
						events,
						wake_up_qs,
						threads):
		
		super().__init__("> spacetr\n")
		self.session = session
		self.Conf = Conf
		self.SqlHan = SqlHan
		self.get_history = get_history
		self.post_history = post_history
		self.BEARER_ACC = BEARER_ACC
		self.events = events
		self.wake_up_qs = wake_up_qs
		self.threads = threads

		self.core_thread_ev = None

		self.ShipHan = None

	def initialise(self):
		
		self.add_menu_item(MenuItem(0, "exit").set_as_exit_option())
		self.add_menu_item(MenuItem(1, "GET", lambda: self._sess_get()))
		self.add_menu_item(MenuItem(2, "POST", lambda: self._sess_post()))
		self.add_menu_item(MenuItem(3, "Deploy Core logic", lambda: self._init_Core()))
		self.add_menu_item(MenuItem(4, "End Core logic", lambda: self._stop_Core()))
		#self.add_menu_item(MenuItem(4, "Register new Agent", lambda: self._sess_post(url=self.Conf.config["sites"]["SPACETRADERS"]["POST"]["REGISTER"],
		#																				headers=self.BEARER_ACC)))
		self.add_menu_item(MenuItem(5, "Options", menu=OptionsSubMenu()))
		# self.add_menu_item(MenuItem(2, "Show hidden menu item", lambda: self.__should_show_hidden_menu__()))
		# self.add_hidden_menu_item(MenuItem(3, "Hidden menu item", lambda: print("I was a hidden menu item")))

	def _init_Core(self):
		self.core_thread_ev = threading.Event()
		core_thr = threading.Thread(target=Core,
									args=(self.session,
											self.Conf,
											self.SqlHan,
											self.core_thread_ev,
											self.events,
											self.wake_up_qs,
											self.threads),
									name="t_core")
		self.threads.append(core_thr)
		self.events.append(self.core_thread_ev)

		core_thr.start()

	
	def _stop_Core(self):
		if self.core_thread_ev is not None:	
			self.core_thread_ev.set()

	
	def _sess_get(self, **kwargs):
		conti = True
		
		# set lib if option available
		if "lib" in super().options.values:	
			kwargs.update({"lib": super().options.values["lib"]})

		if "url" not in kwargs or len(kwargs["url"])==0:
			conti, url, _ = self.__class__.apply_history(self.get_history)
			kwargs.update({"url": url})
		else:
			url = kwargs["url"]
			self.get_history.add(url)
		
		if conti:
			re = self.session.get(**kwargs)
			if re is not None and (re.invalid_reason is None or len(re.Response.content)>0):
				l = re.Response.content.decode()
				if hasattr(re.Response, "status_code") and re.Response.status_code in range(199,211,1):
					self.get_history.add(url)
				print(json.dumps(json.loads(l), indent=4))

	def _sess_post(self, **kwargs):
		conti = True
		data = None

		# set lib if option available
		if "lib" in super().options.values:	
			kwargs.update({"lib": super().options.values["lib"]})

		# set post data mode
		if "post_mode" in super().options.values:
			kwargs.update({"mode": super().options.values["post_mode"]})

		if "url" not in kwargs or len(kwargs["url"])==0:
			# get data in case the endpoint needs specific data
			conti, url, data = self.__class__.apply_history(self.post_history)
			# url is None if user inputed 0
			if not conti:
				return
			kwargs.update({"url": url})

			# update kwargs with needed data
			if data is not None and not isinstance(data, bool):
				kwargs.update({"data": data})

		else:
			url = kwargs["url"]
			self.post_history.add(url)

		if "register" in url:
			kwargs.update({"headers": self.BEARER_ACC})

		if not isinstance(data, bool):
			
			if "data" not in kwargs or len(kwargs["data"])==0:
				conti, data = self.__class__.apply_data()
				kwargs.update({"data": data})
			else:
				data = kwargs["data"]
				self.__class__.save_data(kwargs["data"])

		else:
			kwargs.update({"data": {}})

		if conti:
			print("posting", kwargs)
			re = self.session.post(**kwargs)
			if re is not None and (re.invalid_reason is None or len(re.Response.content)>0):
				l = re.Response.content.decode()
				if hasattr(re.Response, "status_code") and re.Response.status_code in range(199,211,1):
					self.post_history.add(url)
					self.__class__.save_data(data)
				print(json.dumps(json.loads(l), indent=4))

	def __should_show_hidden_menu__(self):
		print("Showing hidden menu item")
		self.show_hidden_menu = True

	def update_menu_items(self):
		if self.show_hidden_menu:
			self.show_menu_item(3)

	def item_text(self, item: 'MenuItem'):
		return "%30s" % item.description

	def item_line(self, index: int, item: 'MenuItem'):
		return "%d: %s" % (index, self.item_text(item))
