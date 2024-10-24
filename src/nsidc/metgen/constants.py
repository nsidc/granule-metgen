# Default configuration values
DEFAULT_CUMULUS_ENVIRONMENT = 'uat'
DEFAULT_STAGING_KINESIS_STREAM = 'nsidc-cumulus-${environment}-ciss_notification'
DEFAULT_STAGING_BUCKET_NAME = 'nsidc-cumulus-${environment}-ingest-staging'
DEFAULT_WRITE_CNM_FILE = False
DEFAULT_CHECKSUM_TYPE = 'SHA256'
DEFAULT_NUMBER = -1

# Configuration sections
SOURCE_SECTION_NAME = 'Source'
COLLECTION_SECTION_NAME = 'Collection'
DESTINATION_SECTION_NAME = 'Destination'
SETTINGS_SECTION_NAME = 'Settings'

# Templates
UMMG_BODY_TEMPLATE = 'src/nsidc/metgen/templates/ummg_body_template.json'
UMMG_TEMPORAL_TEMPLATE = 'src/nsidc/metgen/templates/ummg_temporal_single_template.json'
UMMG_SPATIAL_TEMPLATE = 'src/nsidc/metgen/templates/ummg_horizontal_rectangle_template.json'
CNM_BODY_TEMPLATE = 'src/nsidc/metgen/templates/cnm_body_template.json'
CNM_FILES_TEMPLATE = 'src/nsidc/metgen/templates/cnm_files_template.json'
