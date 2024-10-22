import configparser
import dataclasses
from datetime import datetime, timezone
import os.path
import uuid

from nsidc.metgen import aws
from nsidc.metgen import constants


@dataclasses.dataclass
class Config:
    environment: str
    data_dir: str
    auth_id: str
    version: str
    provider: str
    local_output_dir: str
    ummg_dir: str
    kinesis_stream_name: str
    staging_bucket_name: str
    write_cnm_file: bool
    checksum_type: str
    number: int

    def show(self):
        # TODO add section headings in the right spot (if we think we need them in the output)
        print()
        print('Using configuration:')
        for k,v in self.__dict__.items():
            print(f'  + {k}: {v}')

    def enhance(self, producer_granule_id):
        mapping = dataclasses.asdict(self)
        collection_details = self.collection_from_cmr(mapping)

        mapping['auth_id'] = collection_details['auth_id']
        mapping['version'] = collection_details['version']
        mapping['producer_granule_id'] = producer_granule_id
        mapping['submission_time'] = datetime.now(timezone.utc).isoformat()
        mapping['uuid'] = str(uuid.uuid4())

        return mapping

    # Is the right place for this function?
    def collection_from_cmr(self, mapping):
        # TODO: Use auth_id and version from mapping object to retrieve collection
        # metadata from CMR, including formatted version number, temporal range, and
        # spatial coverage.
        return {
            'auth_id': mapping['auth_id'],
            'version': mapping['version']
        }

def config_parser_factory(configuration_file):
    """
    Returns a ConfigParser by reading the specified file.
    """
    if configuration_file is None or not os.path.exists(configuration_file):
        raise ValueError(f'Unable to find configuration file {configuration_file}')
    cfg_parser = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    cfg_parser.read(configuration_file)
    return cfg_parser


def _get_configuration_value(environment, section, name, value_type, config_parser, overrides):
    """
    Returns a value from the provided config parser; any value for the key that
    is provided in the 'overrides' dictionary will take precedence.
    """
    vars = { 'environment': environment }
    if overrides.get(name) is None:
        if value_type is bool:
            return config_parser.getboolean(section, name)
        elif value_type is int:
            return config_parser.getint(section, name)
        else:
            value = config_parser.get(section, name, vars=vars)
            return value
    else:
        return overrides.get(name)

def configuration(config_parser, overrides, environment=constants.DEFAULT_CUMULUS_ENVIRONMENT):
    """
    Returns a valid Config object that is populated from the provided config
    parser based on the 'environment', and with values overriden with anything
    provided in 'overrides'.
    """
    config_parser['DEFAULT'] = {
        'kinesis_stream_name': constants.DEFAULT_STAGING_KINESIS_STREAM,
        'staging_bucket_name': constants.DEFAULT_STAGING_BUCKET_NAME,
        'write_cnm_file': constants.DEFAULT_WRITE_CNM_FILE,
        'checksum_type': constants.DEFAULT_CHECKSUM_TYPE,
        'number': constants.DEFAULT_NUMBER,
    }
    try:
        return Config(
            environment,
            _get_configuration_value(environment, 'Source', 'data_dir', str, config_parser, overrides),
            _get_configuration_value(environment, 'Collection', 'auth_id', str, config_parser, overrides),
            _get_configuration_value(environment, 'Collection', 'version', int, config_parser, overrides),
            _get_configuration_value(environment, 'Collection', 'provider', str, config_parser, overrides),
            _get_configuration_value(environment, 'Destination', 'local_output_dir', str, config_parser, overrides),
            _get_configuration_value(environment, 'Destination', 'ummg_dir', str, config_parser, overrides),
            _get_configuration_value(environment, 'Destination', 'kinesis_stream_name', str, config_parser, overrides),
            _get_configuration_value(environment, 'Destination', 'staging_bucket_name', str, config_parser, overrides),
            _get_configuration_value(environment, 'Destination', 'write_cnm_file', bool, config_parser, overrides),
            _get_configuration_value(environment, 'Settings', 'checksum_type', str, config_parser, overrides),
            _get_configuration_value(environment, 'Settings', 'number', int, config_parser, overrides),
        )
    except Exception as e:
        return Exception('Unable to read the configuration file', e)

def validate(configuration):
    """
    Validates each value in the configuration.
    """
    validations = [
        ['data_dir', lambda dir: os.path.exists(dir), 'The data_dir does not exist.'],
        ['local_output_dir', lambda dir: os.path.exists(dir), 'The local_output_dir does not exist.'],
        # ['ummg_dir', lambda dir: os.path.exists(dir), 'The ummg_dir does not exist.'],                 ## Not sure what validation to do
        ['kinesis_stream_name', lambda name: aws.kinesis_stream_exists(name), 'The kinesis stream does not exist.'],
        ['staging_bucket_name', lambda name: aws.staging_bucket_exists(name), 'The staging bucket does not exist.'],
    ]
    errors = [msg for name, fn, msg in validations if not fn(getattr(configuration, name))]
    return len(errors) == 0, errors

