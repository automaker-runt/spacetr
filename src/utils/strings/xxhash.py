# xxhash

import xxhash, time


def hash(inp:str) -> str:
	# creates hash and formats it in if {} available

	inp = _val_inp(inp)

	# need to seed it with time
	seed = inp+' '+str(time.time())
	hsh = xxhash.xxh32(seed.encode()).hexdigest()

	return inp.format(hsh)


def getHash(inp:str) -> str:
	# creates hash and returns it

	inp = _val_inp(inp)

	# need to seed it with time
	seed = inp+' '+str(time.time())

	return xxhash.xxh32(seed.encode()).hexdigest()


def getHash64(inp:str) -> str:
	# creates hash and returns it

	inp = _val_inp(inp)

	# need to seed it with time
	seed = inp+' '+str(time.time())

	return xxhash.xxh64(seed.encode()).hexdigest()


def _val_inp(inp) -> str:
	if isinstance(inp, str):
		return inp

	else:
		return str(inp)