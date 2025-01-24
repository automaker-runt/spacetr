# strings
# helper strings functions for sql syntax

def fill_sql_question_m(inp:dict, offset=0) -> str:
	multpl = len(inp.keys())-1+offset
	if multpl < 0:
		qs = ''
	else:	
		qs = multpl*'?, '+'?'
	
	qqs = qs.replace("'", "")

	return qqs