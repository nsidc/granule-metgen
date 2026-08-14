"""
Logging configuration.

Adds a couple of extra log levels for better refinement of output.
"""

import logging


class metgencLogger(logging.getLoggerClass()):
    DEBUG_MINUS = 5
    DEBUG = logging.DEBUG
    INFO_MINUS = 15
    INFO = logging.INFO
    INFO_PLUS = 25

    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)

        logging.addLevelName(logging.DEBUG - 5, "DEBUG_MINUS")
        logging.addLevelName(logging.INFO - 5, "INFO_MINUS")
        logging.addLevelName(logging.INFO + 5, "INFO_PLUS")

    def debug_minus(self, msg, *args, **kwargs):
        if self.isEnabledFor(self.DEBUG_MINUS):
            self._log(self.DEBUG_MINUS, msg, args, **kwargs)

    def info_minus(self, msg, *args, **kwargs):
        if self.isEnabledFor(self.INFO_MINUS):
            self._log(self.INFO_MINUS, msg, args, **kwargs)

    def info_plus(self, msg, *args, **kwargs):
        if self.isEnabledFor(self.INFO_PLUS):
            self._log(self.INFO_PLUS, msg, args, **kwargs)
