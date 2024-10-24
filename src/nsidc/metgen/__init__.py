import logging

logger = logging.getLogger('metgenc')
logger.setLevel("INFO")
console_handler = logging.StreamHandler()
logger.addHandler(console_handler)
