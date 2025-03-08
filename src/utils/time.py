import time, datetime
from threading import Event
from typing import Union


def wait(delay_until:float, interval=0.1, ev_quit: Union[Event, None]=None):
	if ev_quit is None:
		ev_quit = Event()

	# sleeps until defined time
	
	if not isinstance(delay_until, float):
		delay_until = float(delay_until)

	interval = float(interval)
	if delay_until < 161560.0:
		delay_until += time.time()

	while time.time() < delay_until and not ev_quit.is_set():
		time.sleep(interval)


def conv_time_time_to_def(t:float, precision:str="millisecond") -> str:
	
	if precision == "millisecond":
		pres = -9
	elif precision == "second":
		pres = -12
	elif precision == "nanosecond":
		pres = -5
	else:
		raise ValueError("precision is wrong value")

	re = str(datetime.datetime.fromtimestamp(t, datetime.UTC))[:pres]+"Z"
	re = re[:10]+"T"+re[11:]

	return re


def ISO_to_epoch(t:str) -> Union[float, int]:
	if isinstance(t, Union[float, int]):
		return t

	utc_time = datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S.%fZ")
	epoch_time = (utc_time - datetime.datetime(1970, 1, 1)).total_seconds()

	return epoch_time

# def epoch_to_ISO(t:str) -> float:
# 	utc_time = datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S.%fZ")
# 	epoch_time = (utc_time - datetime.datetime(1970, 1, 1)).total_seconds()

# 	return epoch_time


def e(inp, **kwargs):
	if len(str(inp)) <= 10 and len(kwargs) == 0:
		s = int(inp)
		return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(s))
	if len(str(inp)) <= 10 and len(kwargs) > 0:
		if "minute" in kwargs:
			s = int(inp)
			return (s//60+kwargs["minute"])*60
		elif "hour" in kwargs:
			s = int(inp)
			return (s//3600+kwargs["hour"])*3600
		elif "day" in kwargs:
			s = int(inp)
			return (s//86400+kwargs["day"])*86400
		elif "week" in kwargs:
			s = int(inp)
			return ((s//604800+kwargs["week"])*604800)+345600 #	the summand at end offsets first day of unix timestamp being thursday 1 jan and needing few days to get to monday
		elif "month" in kwargs:
			return e(e(int(inp)), month=kwargs["month"])
		elif "year" in kwargs:
			return e(e(int(inp)), year=kwargs["year"])
		else: print("e(): kwargs no key 'minute', 'hour', 'day', 'week', 'month' or 'year' with value int")
	elif len(str(inp)) == 25 and len(kwargs) == 0:
		i = str(inp)
		t = (int(i[0:4]), int(i[5:7]), int(i[8:10]), int(i[11:13]), int(i[14:16]), int(i[17:19]), 0, 0, 0)
		#		year		month		day				hour			minute		second
		return int(str(time.mktime(t)-(int(time.mktime(time.gmtime()))-int(time.mktime(time.localtime()))))[:10])
	elif len(str(inp)) == 25 and len(kwargs) > 0:
		if "minute" in kwargs:
			i = str(inp)
			t = (int(i[0:4]), int(i[5:7]), int(i[8:10]), int(i[11:13]), int(i[14:16])+kwargs["minute"], 0, 0, 0, 0)
			return int(float(str(time.mktime(t)-(int(time.mktime(time.gmtime()))-int(time.mktime(time.localtime()))))[:10]))
		elif "hour" in kwargs:
			i = str(inp)
			t = (int(i[0:4]), int(i[5:7]), int(i[8:10]), int(i[11:13])+kwargs["hour"], 0, 0, 0, 0, 0)
			return int(float(str(time.mktime(t)-(int(time.mktime(time.gmtime()))-int(time.mktime(time.localtime()))))[:10]))
		elif "day" in kwargs:
			i = str(inp)
			t = (int(i[0:4]), int(i[5:7]), int(i[8:10])+kwargs["day"], 0, 0, 0, 0, 0, 0)
			return int(float(str(time.mktime(t)-(int(time.mktime(time.gmtime()))-int(time.mktime(time.localtime()))))[:10]))
		elif "week" in kwargs:
			i = str(inp)
			t = (int(i[0:4]), int(i[5:7]), int(i[8:10]), 0, 0, 0, 0, 0, 0)
			return e(int(str(time.mktime(t)-(int(time.mktime(time.gmtime()))-int(time.mktime(time.localtime()))))[:10]), week=kwargs["week"])
		elif "month" in kwargs:
			i = str(inp)
			t = (int(i[0:4]), int(i[5:7])+kwargs["month"], 1, 0, 0, 0, 0, 0, 0)
			return int(float(str(time.mktime(t)-(int(time.mktime(time.gmtime()))-int(time.mktime(time.localtime()))))[:10]))
		elif "year" in kwargs:
			i = str(inp)
			t = (int(i[0:4])+kwargs["year"], 1, 1, 0, 0, 0, 0, 0, 0)
			return int(float(str(time.mktime(t)-(int(time.mktime(time.gmtime()))-int(time.mktime(time.localtime()))))[:10]))
		else: print("e(): kwargs no key 'minute', 'hour', 'day', 'week', 'month' or 'year' with value int")
