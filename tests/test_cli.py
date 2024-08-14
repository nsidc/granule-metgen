from os import getcwd
from click.testing import CliRunner

from nsidc.cli import cli, info

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
    
    for section in ['Source', 'Collection', 'Destination']:
        assert section in result.output

    for key in ['data_dir', 'ummg_dir', 'auth_id', 'version', 'local_dir', 'kinesis_arn', 's3_url']:
        assert key in result.output
