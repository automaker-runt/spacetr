# meta

def needs_more_pages(inp:dict) -> bool:
	tot = inp["total"]
	pag = inp["page"]
	lim = inp["limit"]

	if tot <= pag*lim:
		return False

	else:
		return True


if __name__ == "__main__":

	print(needs_more_pages({
	        "total": 41,
	        "page": 2,
	        "limit": 20
	    }))