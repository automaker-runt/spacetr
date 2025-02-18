# qhand

import logging.handlers, copy


class QHand(logging.handlers.QueueHandler):


	def prepare(self, record):
		"""
		Prepare a record for queuing. The object returned by this method is
		enqueued.

		The base implementation formats the record to merge the message and
		arguments, and removes unpickleable items from the record in-place.
		Specifically, it overwrites the record's `msg` and
		`message` attributes with the merged message (obtained by
		calling the handler's `format` method), and sets the `args`,
		`exc_info` and `exc_text` attributes to None.

		You might want to override this method if you want to convert
		the record to a dict or JSON string, or send a modified copy
		of the record while leaving the original intact.
		"""
		# The format operation gets traceback text into record.exc_text
		# (if there's exception data), and also returns the formatted
		# message. We can then use this to replace the original
		# msg + args, as these might be unpickleable. We also zap the
		# exc_info, exc_text and stack_info attributes, as they are no longer
		# needed and, if not None, will typically not be pickleable.
		
		# bpo-35726: make copy of record to avoid affecting other handlers in the chain.
		record = copy.copy(record)
		record.message = self.format(record)
		# record.msg = self.msg
		# record.args = self.args
		record.exc_info = None
		record.exc_text = None
		record.stack_info = None
		
		return record


	# def format(self, record):
	# 	"""
    #     Format the specified record.

    #     If a formatter is set, use it. Otherwise, use the default formatter
    #     for the module.
    #     """
    #     if self.formatter:
    #         fmt = self.formatter
    #     else:
    #         fmt = _defaultFormatter
        
    #     return fmt.format(record)
