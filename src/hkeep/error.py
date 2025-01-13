# error

def tb(E:Exception) -> str:
	fstr = f"{E} (line {E.__traceback__.tb_lineno})"

	return fstr