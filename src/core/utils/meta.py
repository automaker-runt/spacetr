# meta

from core.utils import netw

def needs_more_pages(inp:dict) -> bool:
	tot = inp["total"]
	pag = inp["page"]
	lim = inp["limit"]

	if tot <= pag*lim:
		return False

	else:
		return True


def api_get_pages(Objman, url:str, re_dec:dict, log) -> list:
	data = list()

	# prepare while
	limit = False
	page = 0
	url_p = url+"?page={page}"
	url = url_p.format(page=2)
	
	# pull more pages if meta indicates further pages or upping limit
	while needs_more_pages(re_dec["meta"]):
		# go another cycle
		if not limit and "limit" not in url_p:
			page = 2
			suc, re = Objman.get(url=url)
			
			url_p = url_p+"&limit={limit}"

		else:
			if not limit:
				limit = True
				url = url_p.format(page=2, limit=20)

			else:
				page += 1
				url = url_p.format(page=page, limit=20)

			suc, re = Objman.get(url=url)

		
		if suc:
			re_dec = re.Response.json()
			data.extend(re_dec["data"])
		else:
			log.error(f"api_get_pages needs_more_pages failed to get {url}")
			break

	return data


if __name__ == "__main__":

	print(needs_more_pages({
	        "total": 41,
	        "page": 2,
	        "limit": 20
	    }))