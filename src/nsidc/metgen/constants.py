# Default configuration values
DEFAULT_CUMULUS_ENVIRONMENT = 'uat'
DEFAULT_STAGING_KINESIS_STREAM = 'nsidc-cumulus-${environment}-external_notification'
DEFAULT_STAGING_BUCKET_NAME = 'nsidc-cumulus-${environment}-ingest-staging'
DEFAULT_WRITE_CNM_FILE = False
DEFAULT_OVERWRITE_UMMG = False
DEFAULT_CHECKSUM_TYPE = 'SHA256'
DEFAULT_NUMBER = 1000000

# Logging
ROOT_LOGGER = 'metgenc'

# JSON schema locations and versions
CNM_JSON_SCHEMA = 'src/nsidc/metgen/json-schema/cumulus_sns_schema.json'
CNM_JSON_SCHEMA_VERSION = '1.6.1'
UMMG_JSON_SCHEMA = 'src/nsidc/metgen/json-schema/umm-g-json-schema.json'
UMMG_JSON_SCHEMA_VERSION = '1.6.6'

# Configuration sections
SOURCE_SECTION_NAME = 'Source'
COLLECTION_SECTION_NAME = 'Collection'
DESTINATION_SECTION_NAME = 'Destination'
SETTINGS_SECTION_NAME = 'Settings'

# Spatial coverage
DEFAULT_SPATIAL_AXIS_SIZE = 6

# Templates
CNM_BODY_TEMPLATE = 'src/nsidc/metgen/templates/cnm_body_template.json'
CNM_FILES_TEMPLATE = 'src/nsidc/metgen/templates/cnm_files_template.json'
UMMG_BODY_TEMPLATE = 'src/nsidc/metgen/templates/ummg_body_template.json'
UMMG_TEMPORAL_SINGLE_TEMPLATE = 'src/nsidc/metgen/templates/ummg_temporal_single_template.json'
UMMG_TEMPORAL_RANGE_TEMPLATE = 'src/nsidc/metgen/templates/ummg_temporal_range_template.json'
UMMG_SPATIAL_GPOLYGON_TEMPLATE = 'src/nsidc/metgen/templates/ummg_horizontal_gpolygon_template.json'
UMMG_SPATIAL_POINT_TEMPLATE = 'src/nsidc/metgen/templates/ummg_horizontal_point_template.json'
UMMG_SPATIAL_RECTANGLE_TEMPLATE = 'src/nsidc/metgen/templates/ummg_horizontal_rectangle_template.json'
