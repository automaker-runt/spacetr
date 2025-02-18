# ratelimiter
import time


class RateLimiter:


	def __init__(self, max_p_s:int):
		self.max_p_s = max_p_s
		self.gets = list()		

	
	def get(self) -> None:

		# 
		if len(self.gets) < self.max_p_s:
			self.gets.append(time.time())
			
			return

		else:
			while self.gets[0] +1.0 > time.time():
				time.sleep(0.003)
			

			self.gets.pop(0)
			self.gets.append(time.time())
			
			return


	def burst(self) -> None:
		pass