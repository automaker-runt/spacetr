import time, datetime
from typing import Union


def wait(delay_until:float, interval=0.1):
	# sleeps until defined time
	
	if not isinstance(delay_until, float):
		delay_until = float(delay_until)

	interval = float(interval)
	if delay_until < 161560.0:
		delay_until += time.time()

	while time.time() < delay_until:
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
