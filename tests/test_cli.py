from os import getcwd
from click.testing import CliRunner

from nsidc.metgen.cli import cli, info

def test_without_subcommand():
    runner = CliRunner()
    result = runner.invoke(cli)
    assert result.exit_code == 0
    assert 'Usage' in result.output
    assert 'Commands' in result.output
    for subcommand in ['info', 'init', 'process']:
        assert subcommand in result.output

def test_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0

def test_info_requires_config():
    runner = CliRunner()
    result = runner.invoke(cli, ['info'])
    assert result.exit_code != 0

def test_info_with_config():
    runner = CliRunner()
    result = runner.invoke(cli, ['info', '--config', './example/modscg.ini'])
    assert result.exit_code == 0

def test_info_with_config_summarizes():
    runner = CliRunner()
    result = runner.invoke(cli, ['info', '--config', './example/modscg.ini'])

    for section in ['Source']:
        assert section in result.output

    for key in ['Data directory']:
        assert key in result.output
