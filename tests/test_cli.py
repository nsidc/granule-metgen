from unittest.mock import patch

from click.testing import CliRunner
import pytest

from nsidc.metgen.cli import cli


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

def test_process_requires_config(cli_runner):
    result = cli_runner.invoke(cli, ['process'])
    assert result.exit_code != 0

@patch('nsidc.metgen.metgen.aws.post_to_kinesis', return_value = True)
@patch('nsidc.metgen.metgen.validate', return_value = True)
def test_process_with_config(mock, mock2, cli_runner):
    result = cli_runner.invoke(cli, ['process', '--config', './example/modscg.ini'])
    assert result.exit_code == 0
    assert 'Saved CNM message' in result.output
    assert 'Processed granules' in result.output

@patch('nsidc.metgen.metgen.aws.post_to_kinesis', return_value = True)
@patch('nsidc.metgen.metgen.validate', return_value = True)
def test_process_with_granule_limit(mock, mock2, cli_runner):
    result = cli_runner.invoke(cli, ['process', '-n', '2', '--config', './example/modscg.ini'])
    assert result.exit_code == 0
    # TODO: assert it processed two files
