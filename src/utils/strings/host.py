

def getHost(inp:str) -> str:
	if inp.find(":") != -1:		
		if inp[inp.find(":")+3:].find("/") != -1:
			_host = inp[inp.find(":")+3:inp[inp.find(":")+3:].find("/")+inp.find(":")+3]	# "https://developers.binance.com/docs/derivatives/change-log" -> "developers.binance.com"
		else:
			_host = inp[inp.find(":")+3:]	# "https://developers.binance.com"
	else:
		_host = 'cloudfront.net'

	return _host