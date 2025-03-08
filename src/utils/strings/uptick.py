# uptick

from fsys.folderinit.folder import Folder


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


def file_in_folder(inp:str) -> str:
	# only works if filename in inp really exists

	folder, target = inp[:inp.rfind('/')+1], inp[inp.rfind('/')+1:]
	target_fname, fend = target.split('.')

	files = list()
	for f in Folder.get_folder_content(inp[:inp.rfind('/')], filesonly=True):
		if target_fname in f and fend in f and f != target:
			flen = f[len(target_fname):f.rfind('.')]
			flen2 = f[:len(target_fname)]
			if flen.isdigit():	
				files.append((int(flen), flen2))

	files.sort()

	# make of every file in folder with same target_fname a tuple containing its trailing numbers and the target_fname
	#files = [(int(f[len(target_fname):f.rfind('.')]), f[:len(target_fname)]) for f in Folder.get_folder_content(inp[:inp.rfind('/')], filesonly=True) if target_fname in f and fend in f and f != target]

	if len(files) > 0:	
		# combine target_fname with greatest existing trailing number+1 and with fend
		return folder+target_fname+str(sorted(files)[-1][0]+1)+'.'+fend
	else:
		return folder+target_fname+"1."+fend


if __name__ == "__main__":
	print(filename("/home/user/dev/spacetr/test18.sqlite"))