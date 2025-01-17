# shorten

def short(inp:str) -> str:
	# TODO make it use a value from settings

	if len(inp) <= 30:
		
		return inp

	else:

		return '...'+inp[-29:]