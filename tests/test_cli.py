from unittest.mock import patch

import pytest
from click.testing import CliRunner

from nsidc.metgen.cli import cli

INI_FILE = "./fixtures/test.ini"

# Unit tests for the 'cli' module functions.
#
# The test boundary is the cli module's interface with the metgen module, so in
# addition to testing the cli module's behavior, the tests should mock that
# module's functions and assert that cli functions call them with the correct
# parameters, correctly handle their return values, and handle any exceptions
# they may throw.


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_without_subcommand(cli_runner):
    result = cli_runner.invoke(cli)
    # Click returns exit code 2 when no subcommand is provided to a command group
    assert result.exit_code == 2
    assert "Usage" in result.output
    assert "Commands" in result.output
    for subcommand in ["info", "init", "process"]:
        assert subcommand in result.output


def test_help(cli_runner):
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0


def test_info_requires_config(cli_runner):
    result = cli_runner.invoke(cli, ["info"])
    assert result.exit_code != 0


def test_info_with_config(cli_runner):
    result = cli_runner.invoke(cli, ["info", "--config", INI_FILE])
    assert result.exit_code == 0


@patch("nsidc.metgen.config.Config.show")
def test_info_with_config_summarizes(mock, cli_runner):
    result = cli_runner.invoke(cli, ["info", "--config", INI_FILE])
    assert mock.called
    assert result.exit_code == 0


@patch("nsidc.metgen.metgen.process")
def test_process_requires_config(mock, cli_runner):
    result = cli_runner.invoke(cli, ["process"])
    assert not mock.called
    assert result.exit_code != 0


@patch("nsidc.metgen.config.validate")
@patch("nsidc.metgen.metgen.process")
def test_process_with_config_calls_process(mock_validate, mock_process, cli_runner):
    cli_runner.invoke(cli, ["process", "--config", INI_FILE])
    assert mock_process.called


@patch("nsidc.metgen.config.validate")
@patch("nsidc.metgen.metgen.process")
def test_process_with_granule_limit(mock_validate, mock_process, cli_runner):
    number_files = 2
    result = cli_runner.invoke(
        cli, ["process", "-n", str(number_files), "--config", INI_FILE]
    )

    assert mock_process.called
    args = mock_process.call_args.args
    assert len(args) == 1
    configuration = args[0]
    assert configuration.number == number_files
    assert result.exit_code == 0


@patch("nsidc.metgen.config.configuration")
@patch("nsidc.metgen.metgen.process")
@patch("nsidc.metgen.config.validate")
@patch("nsidc.metgen.config.validate_spatial_source")
def test_process_with_no_write_cnm(
    mock_validate_spatial, mock_validate, process_mock, configuration_mock, cli_runner
):
    result = cli_runner.invoke(cli, ["process", "--config", INI_FILE])

    assert configuration_mock.called
    args = configuration_mock.call_args.args
    overrides = args[1]
    assert overrides["write_cnm_file"] is None
    assert result.exit_code == 0


@patch("nsidc.metgen.config.configuration")
@patch("nsidc.metgen.metgen.process")
@patch("nsidc.metgen.config.validate")
@patch("nsidc.metgen.config.validate_spatial_source")
def test_process_with_write_cnm(
    mock_validate_spatial, mock_validate, process_mock, configuration_mock, cli_runner
):
    result = cli_runner.invoke(cli, ["process", "-wc", "--config", INI_FILE])

    assert configuration_mock.called
    args = configuration_mock.call_args.args
    overrides = args[1]
    assert overrides["write_cnm_file"]
    assert result.exit_code == 0


@patch("nsidc.metgen.config.configuration")
@patch("nsidc.metgen.metgen.process")
@patch("nsidc.metgen.config.validate")
@patch("nsidc.metgen.config.validate_spatial_source")
def test_process_with_no_overwrite(
    mock_validate_spatial, mock_validate, process_mock, configuration_mock, cli_runner
):
    result = cli_runner.invoke(cli, ["process", "--config", INI_FILE])

    assert configuration_mock.called
    args = configuration_mock.call_args.args
    overrides = args[1]
    assert overrides["overwrite_ummg"] is None
    assert result.exit_code == 0


@patch("nsidc.metgen.config.configuration")
@patch("nsidc.metgen.metgen.process")
@patch("nsidc.metgen.config.validate")
@patch("nsidc.metgen.config.validate_spatial_source")
def test_process_with_overwrite(
    mock_validate_spatial, mock_validate, process_mock, configuration_mock, cli_runner
):
    result = cli_runner.invoke(cli, ["process", "-o", "--config", INI_FILE])

    assert configuration_mock.called
    args = configuration_mock.call_args.args
    overrides = args[1]
    assert overrides["overwrite_ummg"]
    assert result.exit_code == 0


# TODO: When process raises an exception, cli handles it and displays a message
#       and has non-zero exit code
