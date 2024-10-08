from unittest.mock import patch

from click.testing import CliRunner
import pytest

from nsidc.metgen.cli import cli


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
    assert result.exit_code == 0
    assert 'Usage' in result.output
    assert 'Commands' in result.output
    for subcommand in ['info', 'init', 'process']:
        assert subcommand in result.output

def test_help(cli_runner):
    result = cli_runner.invoke(cli, ['--help'])
    assert result.exit_code == 0

def test_info_requires_config(cli_runner):
    result = cli_runner.invoke(cli, ['info'])
    assert result.exit_code != 0

def test_info_with_config(cli_runner):
    result = cli_runner.invoke(cli, ['info', '--config', './example/modscg.ini'])
    assert result.exit_code == 0

def test_info_with_config_summarizes(cli_runner):
    result = cli_runner.invoke(cli, ['info', '--config', './example/modscg.ini'])

    for key in ['auth_id', 'data_dir', 'environment', 'local_output_dir', 'kinesis_arn', 'provider', 'ummg_dir', 'version']:
        assert key in result.output

@patch('nsidc.metgen.metgen.process')
def test_process_requires_config_does_not_call_process(mock, cli_runner):
    result = cli_runner.invoke(cli, ['process'])
    assert not mock.called
    assert result.exit_code != 0

@patch('nsidc.metgen.metgen.process')
def test_process_with_config_calls_process(mock, cli_runner):
    result = cli_runner.invoke(cli, ['process', '--config', './example/modscg.ini'])
    assert mock.called

@patch('nsidc.metgen.metgen.process')
def test_process_with_granule_limit(process_mock, cli_runner):
    number_files = 2
    result = cli_runner.invoke(cli, ['process', '-n', str(number_files), '--config', './example/modscg.ini'])

    assert process_mock.called
    args = process_mock.call_args.args
    assert len(args) == 1
    configuration = args[0]
    assert configuration.number == number_files
    assert result.exit_code == 0


# TODO: When process raises an exception, cli handles it and displays a message
#       and has non-zero exit code
