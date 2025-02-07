# error

def tb(E:Exception) -> str:
	'''
	__traceback__ is a traceback object with following attributes
	- tb_frame
	- tb_lasti
	- tb_lineno
	- tb_next
	'''
	frame = str(E.__traceback__.tb_frame)
	fstr = f"{E} ({frame[frame.find('file'):frame.rfind('\'')+1]}, line {E.__traceback__.tb_lineno})"

	return fstr