# create
from typing import Union

def normalize_vals(keys: Union[list, tuple], values: Union[list, tuple]) -> dict:
	# normalize values
	di = dict()
	for k, v in zip(keys, values):
		if not isinstance(v, Union[str, int, None]):
			v = str(v)
		di.update({k: v})

	return di


def dict_sql_ins(
			keys: Union[list, tuple],
			values: Union[list, tuple]) -> Union[str, dict]:

	if len(keys) != len(values):
		# case more keys/columns than values
		if len(keys) > len(values):
			# make it be a list, so we can insert at indx
			if not isinstance(values, list):
				values = list(values)

			# fill the values with None, that become NULL in sqlite
			# fill at max_index -1, so in case there is an update field
			# it stays last
			while len(keys) > len(values):
				if "updated" == keys[-1]:	
					indx = len(values)-1
				else:
					indx = 1
				values.insert(indx, None)
		
		else:	
			raise ValueError("more values than keys")

	# bring value data types to nominal
	di = normalize_vals(keys, values)

	# create the where part of insert
	where = str()
	for col in di.keys():
		where += f"{col}=? AND "

	if len(where) != 0:	
		where = where[:-5]

	return where, di


def dict_sql_updt(
			keys: Union[list, tuple],
			values: Union[list, tuple]) -> Union[str, dict]:

	if len(keys) != len(values):
		raise ValueError("key len is not equal value len")

	# bring value data types to nominal
	di = normalize_vals(keys, values)

	# create the set part
	# of update
	set_ = str()
	for k in di.keys():
	    set_ += f'{k}=?, '

	if len(set_) != 0:
		set_ = set_[:-2]

	return set_, di


def dict_sql_sel(
			keys: Union[list, tuple],
			values: Union[list, tuple]) -> Union[str, dict]:

	if len(keys) != len(values):
		raise ValueError("key len is not equal value len")

	# bring value data types to nominal
	di = normalize_vals(keys, values)

	# create the where part or the set part
	# of update
	where = str()
	for k in di.keys():
	    where += f"{k}=? AND "

	if len(where) != 0:
		where = where[:-5]

	return where, di