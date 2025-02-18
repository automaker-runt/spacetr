# multidicts


def make_dict(multi_dict) -> dict:
	# make multidict-like obj a simple dict

	new_dict = {}
	for k, v in multi_dict.multi_items():
		if k not in new_dict:
			new_dict.update({k: v})

		else:
			first_v = new_dict.pop(k)

			new_dict.update({k: [first_v, v]})

	return new_dict