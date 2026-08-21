"""
Logging configuration.

Adds a couple of extra log levels for better refinement of output.
"""

import datetime as dt
import logging
import os.path
import sys

from nsidc.metgen import constants

CONSOLE_FORMAT = "%(message)s"
LOGFILE_FORMAT = "%(asctime)s| %(message)s"


def init_logging(configuration=None, quiet=0):
    """
    Initialize the logger for metgenc.
    """
    metgencLogger.quiet = quiet
    logging.setLoggerClass(metgencLogger)

    logger = logging.getLogger(constants.ROOT_LOGGER)
    logger.setLevel(logger.DEBUG)

    console_level, logfile_level = select_log_level(logger, quiet)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    logger.addHandler(console_handler)

    # Set log directory
    log_dir = constants.DEFAULT_LOG_DIR
    if configuration and configuration.log_dir:
        log_dir = configuration.log_dir

    # Generate filename: metgenc-{name}-{datetime}.log
    config_basename = "metgenc"
    if configuration and configuration.name:
        config_basename = configuration.name

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    log_filename = f"metgenc-{config_basename}-{timestamp}.log"
    log_path = os.path.join(log_dir, log_filename)

    logfile_handler = logging.FileHandler(log_path, "a")
    logfile_handler.setLevel(logfile_level)
    logfile_handler.setFormatter(logging.Formatter(LOGFILE_FORMAT))
    logger.addHandler(logfile_handler)


def select_log_level(logger, quiet=0):
    """
    Set log levels based on command-line input
    Return tuple with (console level, log level)
    """
    match quiet:
        case 1:
            return (logger.INFO, logger.DEBUG)
        case 2:
            return (logger.INFO_PLUS, logger.INFO)
        case _:
            return (logger.INFO_MINUS, logger.DEBUG_MINUS)


class metgencLogger(logging.getLoggerClass()):
    DEBUG_MINUS = 5
    DEBUG = logging.DEBUG
    INFO_MINUS = 15
    INFO = logging.INFO
    INFO_PLUS = 25

    quiet = 0

    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)

        logging.addLevelName(self.DEBUG_MINUS, "DEBUG_MINUS")
        logging.addLevelName(self.INFO_MINUS, "INFO_MINUS")
        logging.addLevelName(self.INFO_PLUS, "INFO_PLUS")

    def debug_minus(self, msg, *args, **kwargs):
        if self.isEnabledFor(self.DEBUG_MINUS):
            self._log(self.DEBUG_MINUS, msg, args, **kwargs)

    def info_minus(self, msg, *args, **kwargs):
        if self.isEnabledFor(self.INFO_MINUS):
            self._log(self.INFO_MINUS, msg, args, **kwargs)

    def info_plus(self, msg, *args, **kwargs):
        if self.isEnabledFor(self.INFO_PLUS):
            self._log(self.INFO_PLUS, msg, args, **kwargs)
