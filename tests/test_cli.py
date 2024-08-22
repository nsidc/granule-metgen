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

    for section in ['Source', 'Destination']:
        assert section in result.output

    for key in ['Data directory', 'Kinesis ARN', 'S3 URL']:
        assert key in result.output
