# netw

# helper functions

def validate_re(resp, logger, err_msg:str) -> bool:
		if resp is not None and (resp.invalid_reason is None or len(resp.Response.content)>0):
			if hasattr(resp.Response, "status_code") and resp.Response.status_code in range(199,211,1):
				return True

		logger(f"{err_msg} ({resp.Response._reqID})")

		return False

