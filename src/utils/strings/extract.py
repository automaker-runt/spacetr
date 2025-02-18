# extract
from typing import Union


def keyw(inp:str) -> list:
	def _next_item(inp:str) -> Union [bool, str]:
		if "{" in inp and inp.count("{") == inp.count("}"):
			open_indx = inp.find("{")
			close_indx = inp.find("}")
			
			# bool for found or not, item found, rest of string
			return True, inp[open_indx+1:close_indx], inp[close_indx+1:]

		else:
			return False, '', ''

	re_li = list()
	s = inp

	while len(s)>0:
		re, item, s = _next_item(s)
		if re:
			re_li.append(item)

	return re_li