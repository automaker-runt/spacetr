# create


def list_or_same_col(
				li:list,
				colname:str) -> str:

	# li can also be a tuple
	
	if len(li) > 0:	
		com = f"{colname}=?"+(len(li)-1)*f" OR {colname}=?"

	else:
		return ''

	return com


if __name__ == "__main__":
	n = [1,2,3]
	b = [1]
	c = []

	print(f"SELECT id FROM mounts WHERE {list_or_same_col(n, "symbol")};")
	print(f"SELECT id FROM mounts WHERE {list_or_same_col(c, "symbol")};")
