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

	s = f"INSERT INTO {table} {get_str_sql_ins_cols(di)} VALUES ({fill_sql_question_m(di)});"

	return s


def get_str_sql_ins_cols(di:dict) -> str:
	
	cols = str(tuple(di.keys())).replace("'", "")
	if len(di.keys()) == 1:
		cols = cols.replace(',', '')

	return cols


def get_str_sql_sel_cols(di:dict) -> str:
	
	return get_str_sql_ins_cols(di).replace('(', '').replace(')', '')