# marketdata
import time
from utils.time import e


def cycle(update:int=30):
	hour0 = e(int(time.time()), hour=0)

	if update == 30 and int(time.time())-hour0 > 1800:
		return hour0+1800
			
	return hour0
