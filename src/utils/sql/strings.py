# strings
# helper strings functions for sql syntax and other

def fill_sql_question_m(inp:dict, offset=0) -> str:
	multpl = len(inp.keys())-1+offset
	if multpl < 0:
		qs = ''
	else:	
		qs = multpl*'?, '+'?'
	
	qqs = qs.replace("'", "")

	return qqs


def get_str_sql_ins(table:str, di:dict) -> str:

	cols = str(tuple(di.keys())).replace("'", "")
	if len(di.keys()) == 1:
		cols = cols.replace(',', '')
	com = f"INSERT INTO {table} {cols} VALUES ({fill_sql_question_m(di)});"

	return com