# misc
'''
special functions to use with logger in more individual way
'''

# from hkeep.error import tb
# from hkeep.log.logger import get_logger


def adjust_sql_sel_outp_loglvl(tup:tuple, mapper:dict) -> list:
	# transform tuple into list
	line = list(tup)
	# so we can replace loglvl with a lfjust loglvl
	line[mapper["loglvl"]] = line[mapper["loglvl"]].ljust(5)

	return line


def adjust_sql_sel_outp_col_order(sql_outp_col_order:list) -> list:
	# deleting the <table>. prefix from potential <table>.<column>
	# in the list

	for indx in range(len(sql_outp_col_order)):
		if sql_outp_col_order[indx].find('.') != -1:
			sql_outp_col_order[indx] = sql_outp_col_order[indx][sql_outp_col_order[indx].find('.')+1:]

	# sql_outp_col_order[sql_outp_col_order.index("log.id")] = "id"

	return sql_outp_col_order