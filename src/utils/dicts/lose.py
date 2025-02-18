# lose
import json

from typing import Union


def keys(inp:dict, to_lose: Union[str, list, tuple, set]) -> Union[dict, list]:
	# type check di
	if not isinstance(inp, dict):
		raise TypeError("inp not a dict")

	# check in inp for keys that have forms of whatever is in to_lose
	if isinstance(to_lose, str):
		to_lose = [to_lose]

	def level_search(di:dict, li:list):
		for n, k in enumerate(list(di.keys())):

			# find any match on this level, add to results
			if any(i.lower() in k.lower() for i in to_lose):
				li.append((n, k))

			# there is a deeper dict level
			# recursive exec on that level
			elif isinstance(di[k], dict):
				re = (k, level_search(di[k], list()))
				if len(re[1]) > 0:	
					li.append(re)

		return li


	def replace(_di:dict, res:list, _ids:list) -> dict:
		for item in res:
			# int indicates the key is on this dict level
			if isinstance(item[0], int):
				_ids.append((item[1], _di[item[1]]))
				_di.update({item[1]: ''})

			# str indicates this key has another dict under it
			# recursive exec on that level
			# update the key with the result from that level
			elif isinstance(item[0], str):
				_di.update({item[0]: replace(_di[item[0]], item[1], _ids)})

		return _di


	# search for the keys
	results = level_search(inp, list())

	if len(results) > 0:	
		ids = list()

		# replace the keys using results
		inp = replace(inp, results, ids)

		if len(ids) == 1:
			ids = ids[0][1]

	else:
		ids = 0

	inp = json.dumps(inp, indent=2)
	

	#return results, inp, ids
	return inp, ids


if __name__ == "__main__":

# 	test = {
#   "args": {}, 
#   "headers": {
#     "Accept": "*/*", 
#     "Accept-Encoding": "", 
#     "Host": "httpbin.org", 
#     "User-Agent": "python-httpx/0.28.1", 
#     "X-Amzn-Trace-Id": "Root=1-67a265b9-34e6eda328f3a8d17ca891872",
#     "User-Agent": {
#     	"blabla": "wef3f45e",
#     	"X-Youtu.be-Trace-Id": "testing34095u43fß",
#     	"X-goog.le-TraceId": "goog34095u43fß"
#     }
#   }, 
#   "origin": "5.12.159.134", 
#   "url": "https://httpbin.org/get",
#   "Trace-Id": "Root=1-67a265b9-34e6eda328f3a8d17ca71234"
# }

	test = {
  "args": {}, 
  "headers": {
    "Accept": "*/*", 
    "Accept-Encoding": "", 
    "Host": "httpbin.org", 
    "User-Agent": "python-httpx/0.28.1"
  }, 
  "origin": "5.12.159.134", 
  "url": "https://httpbin.org/get"
}

	res, new, values = keys(test, ("Trace-Id", "traceid"))

	print(res)
	print()
	print(json.dumps(new, indent=4))
	print()
	print(values)
