# links
from typing import Union


def needs_format(inp:str) -> bool:
	if "{" in inp and inp.count("{") == inp.count("}"):
		return True
		
	else:
		return False


def is_valid(inp:str) -> bool:
	if all(("http" in inp,
			"//" in inp,
			":" in inp
			)):
		return True

	else:
		return False


if __name__ == "__main__":
	from utils.strings import extract
	t = "https://api.spacetraders.io/v2/systems/{systemSymbol}/waypoints/{waypointSymbol}"
	# extract_keyw(t) returns ["systemSymbol", "waypointSymbol"]

	if needs_format(t):
		li = extract.keyw(t)

		for i in li:	
			print(i)