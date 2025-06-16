"""
Constant values used throughout the `nsidc.metgen` package's submodules.
"""

# Default configuration values
DEFAULT_CUMULUS_ENVIRONMENT = "uat"
DEFAULT_KINESIS_PARTITION_KEY = "metgenc-duck"
DEFAULT_STAGING_KINESIS_STREAM = "nsidc-cumulus-${environment}-external_notification"
DEFAULT_STAGING_BUCKET_NAME = "nsidc-cumulus-${environment}-ingest-staging"
DEFAULT_WRITE_CNM_FILE = False
DEFAULT_OVERWRITE_UMMG = False
DEFAULT_CHECKSUM_TYPE = "SHA256"
DEFAULT_NUMBER = 1000000
DEFAULT_DRY_RUN = False
DEFAULT_BROWSE_REGEX = "_brws"
DEFAULT_COLLECTION_GEOMETRY_OVERRIDE = False

# Logging
ROOT_LOGGER = "metgenc"

# Currently we support one CMR production cloud provider (NSIDC_CPRD) and one
# UAT cloud provider (NSIDC_CPRD).
CMR_PROD_PROVIDER = "NSIDC_CPRD"
CMR_UAT_PROVIDER = "NSIDC_CUAT"

# JSON schema locations and versions
CNM_JSON_SCHEMA = ("nsidc.metgen.json-schema", "cumulus_sns_schema.json")
CNM_JSON_SCHEMA_VERSION = "1.6.1"
UMMG_JSON_SCHEMA = ("nsidc.metgen.json-schema", "umm-g-json-schema.json")
UMMG_JSON_SCHEMA_VERSION = "1.6.6"

# Configuration sections
SOURCE_SECTION_NAME = "Source"
COLLECTION_SECTION_NAME = "Collection"
DESTINATION_SECTION_NAME = "Destination"
SETTINGS_SECTION_NAME = "Settings"

# File name defaults
PREMET_SUFFIX = ".premet"
SPATIAL_SUFFIX = ".spatial"
SPO_SUFFIX = ".spo"
CSV_SUFFIX = ".csv"
NETCDF_SUFFIX = ".nc"

# Spatial coverage
DEFAULT_SPATIAL_AXIS_SIZE = 6
GRANULE_SPATIAL_REP = "GranuleSpatialRepresentation"
CARTESIAN = "CARTESIAN"
GEODETIC = "GEODETIC"

# UMM-G keys
UMMG_ADDITIONAL_ATTRIBUTES = "AdditionalAttributes"

# Location of spatial and temporal information in collection metadata retrieved from CMR
GRANULE_SPATIAL_REP_PATH = ["SpatialExtent", GRANULE_SPATIAL_REP]
SPATIAL_EXTENT_PATH = [
    "SpatialExtent",
    "HorizontalSpatialDomain",
    "Geometry",
    "BoundingRectangles",
]
TEMPORAL_EXTENT_PATH = ["TemporalExtents"]

# Templates
CNM_BODY_TEMPLATE = ("nsidc.metgen.templates", "cnm_body_template.txt")
CNM_FILES_TEMPLATE = ("nsidc.metgen.templates", "cnm_files_template.txt")
UMMG_BODY_TEMPLATE = ("nsidc.metgen.templates", "ummg_body_template.txt")
UMMG_TEMPORAL_SINGLE_TEMPLATE = (
    "nsidc.metgen.templates",
    "ummg_temporal_single_template.txt",
)
UMMG_TEMPORAL_RANGE_TEMPLATE = (
    "nsidc.metgen.templates",
    "ummg_temporal_range_template.txt",
)
UMMG_SPATIAL_GPOLYGON_TEMPLATE = (
    "nsidc.metgen.templates",
    "ummg_horizontal_gpolygon_template.txt",
)
UMMG_SPATIAL_POINT_TEMPLATE = (
    "nsidc.metgen.templates",
    "ummg_horizontal_point_template.txt",
)
UMMG_SPATIAL_RECTANGLE_TEMPLATE = (
    "nsidc.metgen.templates",
    "ummg_horizontal_rectangle_template.txt",
)
UMMG_ADDITIONAL_ATTRIBUTES_TEMPLATE = (
    "nsidc.metgen.templates",
    "ummg_additional_attributes_template.txt",
)
