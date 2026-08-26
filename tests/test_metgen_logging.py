import logging
from unittest.mock import patch

import pytest

from nsidc.metgen import constants, metgen, metgen_logging

# Unit tests for the 'logging' module functions.
#
NO_Q = 0
ONE_Q = 1
TWO_Q = 2


def current_logfile_level(logger):
    level = None
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            level = handler.level

    return level


@pytest.fixture
def ledger_list():
    successful_action = metgen.Action(
        name="successful_action", successful=True, message="we did it!"
    )
    failed_action = metgen.Action(
        name="failed_action", successful=False, message="too bad"
    )

    return [
        metgen.Ledger(
            metgen.Granule("failed granule"),
            actions=[successful_action, failed_action],
            successful=False,
        ),
        metgen.Ledger(
            metgen.Granule("successful granule"),
            actions=[successful_action, successful_action],
            successful=True,
        ),
    ]


@patch("logging.FileHandler._open")
def test_q_level_saved_by_logger(filemock):
    metgen_logging.init_logging(None, ONE_Q)
    logger = logging.getLogger(constants.ROOT_LOGGER)
    assert logger.__class__.quiet == ONE_Q


def test_logging_level_varies_by_q():
    zero_console_level, zero_log_level = metgen_logging.select_log_level(NO_Q)
    one_console_level, one_log_level = metgen_logging.select_log_level(ONE_Q)
    two_console_level, two_log_level = metgen_logging.select_log_level(TWO_Q)

    assert zero_console_level < one_console_level < two_console_level
    assert zero_log_level < one_log_level < two_log_level
    assert zero_console_level != zero_log_level
    assert one_console_level != one_log_level
    assert two_console_level != two_log_level


@patch("logging.FileHandler._open")
def test_quiet_ledger_only_shows_failed_action(filemock, ledger_list, caplog):
    metgen_logging.init_logging(None, ONE_Q)
    logger = logging.getLogger(constants.ROOT_LOGGER)

    logfile_level = current_logfile_level(logger)
    assert logfile_level == metgen_logging.metgencLogger.DEBUG

    with caplog.at_level(logfile_level):
        metgen.log_ledger(ledger_list[0])
        assert "successful_action" not in caplog.text
        assert "failed_action" in caplog.text


@patch("logging.FileHandler._open")
def test_super_quiet_ledger_only_shows_failed_granule_entry(
    filemock, ledger_list, caplog
):
    metgen_logging.init_logging(None, TWO_Q)
    logger = logging.getLogger(constants.ROOT_LOGGER)

    logfile_level = current_logfile_level(logger)
    assert logfile_level == metgen_logging.metgencLogger.INFO

    with caplog.at_level(logfile_level):
        metgen.log_ledger(ledger_list[0])
        assert "failed granule" in caplog.text
        assert "successful_action" not in caplog.text
        assert "failed_action" not in caplog.text


@patch("logging.FileHandler._open")
def test_default_log_shows_all_actions(filemock, ledger_list, caplog):
    metgen_logging.init_logging(None, NO_Q)
    logger = logging.getLogger(constants.ROOT_LOGGER)
    logfile_level = current_logfile_level(logger)
    assert logfile_level == metgen_logging.metgencLogger.DEBUG_MINUS

    with caplog.at_level(logfile_level):
        for ledger in ledger_list:
            metgen.log_ledger(ledger)

        assert "failed granule" in caplog.text
        assert "successful granule" in caplog.text
        assert caplog.text.count("successful_action") == 3
        assert caplog.text.count("failed_action") == 1
