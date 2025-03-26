# ratelimiter
import time


class RateLimiter:


	def __init__(self, max_p_s:int):
		self.max_p_s = max_p_s
		self.gets = list()		

	
	def get(self) -> None:

		# add to list if not at max
		if len(self.gets) < self.max_p_s:
			self.gets.append(time.time())
			
			return

		else:
			if self.gets[0] +1.0 > time.time():
				time.sleep(max(0.001,
				   			self.gets[0] +1.0 - time.time()))			

			self.gets.pop(0)
			self.gets.append(time.time())
			
			return


	def burst(self) -> None:
		pass