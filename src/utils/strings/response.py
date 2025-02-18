

def _log_helper_valid(obj, pref:str) -> str:

	reason = ''
	if hasattr(obj.Response, 'reason'):
		reason = obj.Response.reason
	s = f"{pref}: code({obj.Response.status_code}), session({obj.Session}), reason({reason}), lib({obj.lib}), mode({obj.mode}), sent_data({obj.data}), respID({obj._respID}), reqID({obj.Response._reqID}), url({obj.url})"

	return s


def _log_helper_valid_error(obj, pref:str) -> str:

	reason = ''
	if hasattr(obj.Response, 'reason'):
		reason = obj.Response.reason
	s = f"{pref}: session({obj.Session}), lib({obj.lib}), mode({obj.mode}), sent_data({obj.data}), respID({obj._respID}), reqID({obj.Response._reqID}), url({obj.url})"

	return s
