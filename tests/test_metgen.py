from configparser import ConfigParser

import pytest

from nsidc import instameta


def test_banner():
    assert len(instameta.banner()) > 0

def test_config_parser_without_filename():
    with pytest.raises(ValueError):
        instameta.config_parser(None)

def test_config_parser_return_type():
    result = instameta.config_parser('foo.ini')

    assert isinstance(result, ConfigParser)

def test_config_from_config_parser():
    cfg_parser = ConfigParser()
    cfg_parser['Source'] = { 'data_dir': 'bar' }

    config = instameta.configuration(cfg_parser)

    assert isinstance(config, instameta.Config)

def test_config_with_values():
    cfg_parser = ConfigParser()
    cfg_parser['Source'] = { 'data_dir': '/data/example' }

    config = instameta.configuration(cfg_parser)

    assert config.source_data_dir == '/data/example'
