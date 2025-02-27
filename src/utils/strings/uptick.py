# uptick


def filename(inp:str) -> str:
	# filename has to have a dot - file type ending

	f_type = inp[inp.rfind('.'):]
	fp_fname = inp[:inp.rfind('.')]

	# get current number
	rev = 0
	temp_fname = fp_fname
	while temp_fname[-1].isdigit():
		rev -= 1
		temp_fname = temp_fname[:-1]

	if rev == 0:
		curr_number = 0
		fp_fname = fp_fname
	else:	
		curr_number = int(fp_fname[rev:])
		fp_fname = fp_fname[:rev]

	# add 1 to curr_number and concat back onto fp_fname
	new_fp_fname = fp_fname+f"{str(curr_number+1)}"+f_type

	return new_fp_fname



if __name__ == "__main__":
	print(filename("/home/user/dev/spacetr/test18.sqlite"))