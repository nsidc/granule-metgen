# MetGenC README.md Table of contents
- [MetGenC](#metgenc)
  * [Level of Support](#level-of-support)
  * [Accessing the OPS MetGenC VM and Tips and Assumptions](#accessing-the-ops-metgenc-vm-and-tips-and-assumptions)
  * [Assumptions for netCDF files for MetGenC](#assumptions-for-netcdf-files-for-metgenc)
  * [MetGenC .ini File Assumtions](#metgenc-ini-file-assumtions)
  * [NetCDF Attributes MetGenC Relies upon to generate UMM-G json files](#netcdf-attributes-metgenc-relies-upon-to-generate-umm-g-json-files)
    + [How to query a netCDF file for presence of MetGenC-Required Attributes](#how-to-query-a-netcdf-file-for-presence-of-metgenc-required-attributes)
  * [Geometry Logic](#geometry-logic)
    + [Geometry Rules](#geometry-rules)
    + [Geometry Logic and Expectations Table](#geometry-logic-and-expectations-table)
  * [Running MetGenC: Its Commands In-depth](#running-metgenc-its-commands-in-depth)
    + [help](#help)
    + [init](#init)
        * [INI RULES](#ini-rules)
      - [Required and Optional Configuration Elements](#required-and-optional-configuration-elements)
      - [Granule and Browse regex](#granule-and-browse-regex)
        * [INI File Example 1: Use of granule_regex for multi-file granules with no browse](#ini-file-example-1-use-of-granule_regex-for-multi-file-granules-with-no-browse)
        * [INI File Example 2: Single-file granule with good file names and no browse-omit browse_regex and granule_regex](#ini-file-example-2-single-file-granule-with-good-file-names-and-no-browse-omit-browse_regex-and-granule_regex)
        * [INI File Example 3: Single-file granule with good file names and browse images-omit granule_regex](#ini-file-example-3-single-file-granule-with-good-file-names-and-browse-images-omit-granule_regex)
        * [INI File Example 4: Use of granule_regex and browse_regex for single-file granules with interrupted file names](#ini-file-example-4-use-of-granule_regex-and-browse_regex-for-single-file-granules-with-interrupted-file-names)
        * [INI File Example 5: Use of granule_regex and browse_regex for multi-file granules with variables in file names](#ini-file-example-5-use-of-granule_regex-and-browse_regex-for-multi-file-granules-with-variables-in-file-names)
      - [Using Premet and Spatial Files](#using-premet-and-spatial-files)
      - [Setting Collection Spatial Extent as Granule Spatial Extent](#setting-collection-spatial-extent-as-granule-spatial-extent)
      - [Setting Collection Temporal Extent as Granule Temporal Extent](#setting-collection-temporal-extent-as-granule-temporal-extent)
      - [Spatial Polygon Generation](#spatial-polygon-generation)
        * [Example Spatial Polygon Generation Configuration](#example-spatial-polygon-generation-configuration)
    + [info](#info)
      - [Example running info](#example-running-info)
    + [process](#process)
      - [Examples running process](#examples-running-process)
      - [Troubleshooting metgenc process](#troubleshooting-metgenc-process)
    + [validate](#validate)
      - [Example running validate](#example-running-validate)
    + [Pretty-print a json file in your shell](#pretty-print-a-json-file-in-your-shell)
  * [For Developers](#for-developers)
    + [Contributing](#contributing)
      - [Requirements](#requirements)
      - [Installing Dependencies](#installing-dependencies)
      - [Run tests](#run-tests)
      - [Run tests when source changes](#run-tests-when-source-changes)
      - [Running the linter for code style issues](#running-the-linter-for-code-style-issues)
      - [Running the code formatter](#running-the-code-formatter)
      - [Ruff integration with your editor](#ruff-integration-with-your-editor)
      - [Spatial Polygon Diagnostic Tool](#spatial-polygon-diagnostic-tool)
      - [Releasing](#releasing)

<p align="center">
  <img alt="NSIDC logo" src="https://nsidc.org/themes/custom/nsidc/logo.svg" width="150" />
</p>

# MetGenC

![build & test workflow](https://github.com/nsidc/granule-metgen/actions/workflows/build-test.yml/badge.svg)
![publish workflow](https://github.com/nsidc/granule-metgen/actions/workflows/publish.yml/badge.svg)
[![Documentation Status](https://readthedocs.org/projects/granule-metgen/badge/?version=latest)](https://granule-metgen.readthedocs.io/en/latest/?badge=latest)
[![Documentation Status](https://readthedocs.org/projects/granule-metgen/badge/?version=stable)](https://granule-metgen.readthedocs.io/en/stable/?badge=stable)

The `MetGenC` toolkit enables Operations staff and data
producers to create metadata files conforming to NASA's Common Metadata Repository UMM-G
specification and ingest data directly to NASA EOSDIS’s Cumulus archive. Cumulus is an
open source cloud-based data ingest, archive, distribution, and management framework
developed for NASA's Earth Science data.

## Level of Support

This repository is fully supported by NSIDC. If you discover any problems or bugs,
please submit an Issue. If you would like to contribute to this repository, you may fork
the repository and submit a pull request.

See the [LICENSE](LICENSE.md) for details on permissions and warranties. Please contact
nsidc@nsidc.org for more information.

## Accessing the OPS MetGenC VM and Tips and Assumptions
* from nusnow:
  `$ vssh production metgenc`

* a one-swell-foop command line to kick off everything you need to run MetGenC:
  ```
  for processing in uat
  cd metgenc;source .venv/bin/activate;source metgenc-env.sh cumulus-uat

  or for processing in prod
  cd metgenc;source .venv/bin/activate;source metgenc-env.sh cumulus-prod
  ```
BE AWARE: IF YOU'BE BEEN TESTING/INGEST CUAT INGEST, WHEN YOU'RE READY TO INGEST TO CPRD, MAKE SURE TO RUN `source metgenc-env.sh cumulus-prod`. 
You need to have the right credentials sourced before processing will succeed to that environment!!
If the creds aren't pointing to the right environment, MetGenC will return:
```
* The kinesis stream does not exist.
* The staging bucket does not exist.
```

Commands within the above one-liner detailed:
* CD Into, and activate, the venv:

        $ cd metgenc
        $ source .venv/bin/activate

* Before you run end-to-end ingest, be sure to source the AWS credentials:

        $ source metgenc-env.sh cumulus-<uat or prod>

Available profiles are `cumulus-uat` and `cumulus-prod`.

  If you think you've already run it but can't remember, run the following:

            $ aws configure list

  The output will either indicate that you need to source your credentials by returning:

  ```
  Name                    Value             Type    Location
  ----                    -----             ----    --------
  profile             <not set>             None    None
  access_key          <not set>             None    None
  secret_key          <not set>             None    None
  region              <not set>             None    None
  ```
  Or it'll show that you're all set (AWS comms-wise) for ingesting to Cumulus by
  returning the following:

  ```
  Name                         Value             Type    Location
  ----                         -----             ----    --------
  profile                 cumulus-<uat or prod>   env    ['AWS_DEFAULT_PROFILE', 'AWS_PROFILE']
  access_key     ****************SQXY             env
  secret_key     ****************cJ+5             env
  region                    us-west-2     config-file    ~/.aws/config
  ```



## Assumptions for netCDF files for MetGenC

* NetCDF files have an extension of `.nc` (per CF conventions).
* Projected spatial information is available in coordinate variables having
  a `standard_name` attribute value of `projection_x_coordinate` or
  `projection_y_coordinate` attribute.
* (y[0],x[0]) represents the upper left corner of the spatial coverage.
* Spatial coordinate values represent the center of the area covered by a measurement.
* Only one coordinate system is used by all data variables in all science files
  (i.e. only one grid mapping variable is present in a file, and the content of
  that variable is the same in every science file).

## MetGenC .ini File Assumtions
* A `pixel_size` attribute is needed in a data set's .ini file when gridded science files don't include a GeoTransform attribute in the grid mapping variable. The value specified should be just a number—no units (m, km) need to be specified since they're assumed to be the same as the units of those defined by the coordinate variables in the data set's science files.
  * e.g., `pixel_size = 25`
* Date/time strings can be parsed using `datetime.fromisoformat`
* The checksum_type must be SHA256

## NetCDF Attributes MetGenC Relies upon to Generate UMM-G json Files
CF Conventions and NSIDC Guidelines (=NSIDC Guidelines for netCDF Attributes) are the driving forces behind emphatically
suggesting data producers include the Attributes used by MetGenC in their netCDF files.

- **Required** required
- **RequiredC** conditionally required
- **R+** highly or strongly recommended
- **R** recommended
- **S** suggested

| Attribute used by MetGenC (location in netCDF file)   | CF Conventions | NSIDC Guidelines | Notes   |
| ----------------------------- | -------------- | ---------------- | ------- |
| time_coverage_start (global)  |                | R                | 1, OC, P   |
| time_coverage_end (global)    |                | R                | 1, OC, P   |
| grid_mapping_name (variable)  | RequiredC      | R+               | 2       |
| crs_wkt (variable with `grid_mapping_name` attribute)      |  | R     | 3       |
| GeoTransform (variable with `grid_mapping_name` attribute) |  | R     | 4, OC   |
| geospatial_lon_min (global)   |                | R                | 7    |
| geospatial_lon_max (global)   |                | R                | 7    |
| geospatial_lat_min (global)   |                | R                | 7    |
| geospatial_lat_max (global)   |                | R                | 7    |
| geospatial_bounds (global)    |                | R                | 8, OC |
| geospatial_bounds_crs (global) |               | R                | 9    |
| standard_name, `projection_x_coordinate` (variable) |  | RequiredC  |    | 5       |
| standard_name, `projection_y_coordinate` (variable) |  | RequiredC  |    | 6       |

Notes column key:

 OC = Optional configuration attributes (or elements of them) that may be represented
   in an .ini file in order to allow "nearly" compliant netCDF files to be run with MetGenC
   without premet/spatial files. See [Required and Optional Configuration Elements](#required-and-optional-configuration-elements)

 P = Premet file attributes that may be specified in a premet file; when used, a
  `premet_dir`path must be defined in the .ini file.

 1 = Used by MetGenC to populate the time begin and end UMM-G values, eliminating the need
  for input premet files. If not included in the netCDF global attributes, OC .ini 
  attributes can be specified: `time_start_regex` in lieu of time_coverage_start and
  `time_coverage_duration` in lieu of time_coverage_end, for their use and caveats see
  [Required and Optional Configuration Elements](#required-and-optional-configuration-elements).

 2 = A grid mapping variable is required if the horizontal coordinate variables aren't
   longitude and latitude and the intent of the data provider is to geolocate
   the data. `grid_mapping` and `grid_mapping_name` allow programmatic identification of
   the variable holding information about the horizontal coordinate reference system.

 3 = The `crs_wkt` ("coordinate referenc system well known text") value is handed to the
   `CRS` and `Transformer` modules in `pyproj` to conveniently deal
   with the reprojection of (y,x) values to EPSG 4326 (lon, lat) values.

 4 = The `GeoTransform` value provides the pixel size per data value, which is then used
   to calculate the padding added to x and y values to create a GPolygon enclosing all
   of the data; OC .ini attribute is `pixel_size` = <value>.

 5 = The values of the coordinate variable identified by the `standard_name` attribute
   with a value of `projection_x_coordinate` are reprojected and thinned to create a
   GPolygon, bounding rectangle, etc.

 6 = The values of the coordinate variable identified by the `standard_name` attribute
   with a value of `projection_y_coordinate` are reprojected and thinned to create a
   GPolygon, bounding rectangle, etc.

 7 = When a collection's GranuleSpatialRepresentation is defined as Cartesian,
   MetGenC will generate a bounding rectangle spatial representation using the
   NetCDF file's geospatial_lat_max-min, geospatial_lon_max-min global attributes.

 8 = The `geospatial_bounds` netCDF file global attribute contains spatial boundary information as a
   WKT POLYGON string. When present and `prefer_geospatial_bounds = true` is set in the
   .ini file, MetGenC will use this attribute instead of coordinate variable values to generate
   spatial representations of granules in collections with a GEODETIC (= gpolygon) granule spatial representation.
   If the `geospatial_bounds_crs` attribute is also present in netCDF files, coordinates
   will be transformed to EPSG:4326 if needed. OC .ini attributes for this are `time_start_regex` and `time_coverage_duration`.

 9 = The `geospatial_bounds_crs` netCDF file global attribute specifies the coordinate reference system
   for the coordinates in the `geospatial_bounds` global attribute. It can be an EPSG identifier (e.g., "EPSG:4326")
   or other CRS format. When present, MetGenC will transform `geospatial_bounds` coordinates to EPSG:4326 if needed.
   **If `geospatial_bounds` is `true` and no `geospatial_bounds_crs` attribute exists, the
   coordinates in the `geospatial_bounds` attribute are assumed to represent points in EPSG:4326.**

### How to query a netCDF file for presence of MetGenC-Required Attributes
On V0 wherever the data are staged (/disks/restricted_ftp or /disks/sidads_staging, etc.) you
can run ncdump to check whether a netCDF representative of the collection's files contains the
MetGenC-required attributes. When not reported, that attribute will have to be accommodated by
its associated .ini attribute being added to the .ini file. See [Required and Optional Configuration Elements](#required-and-optional-configuration-elements)
for full details/descriptions of these.
```
ncdump -h <file name.nc> | grep -e time_coverage_start -e time_coverage_end -e GeoTransform -e crs_wkt -e spatial_ref -e grid_mapping_name -e geospatial_bounds -e geospatial_bounds_crs -e 'standard_name = "projection_y_coordinate"' -e 'standard_name = "projection_x_coordinate"'
```

## Geometry Logic

The geometry behind the granule-level spatial representation (point, gpolygon, or bounding
rectangle) required for a data set can be implemented by MetGenC via either: file-level metadata
(such as a CF/NSIDC Compliant netCDF file), `.spatial` / `.spo` files, or
its collection-level spatial representation.

When MetGenC is run with netCDF files that are
both CF and NSIDC Compliant (for those requirements, refer to the table:
[NetCDF Attributes Used to Populate the UMM-G files generated by MetGenC](#netcdf-attributes-used-to-populate-the-umm-g-files-generated-by-metgenc))
information from within the file's metadata will be used to generate an appropriate
gpolygon or bounding rectangle for each granule.

In some cases, non-netCDF files, and/or netCDF files that are non-CF or non-NSIDC
compliant will require an operator to define or modify data set details expressed through
attributes in an .ini file, in other cases an operator will need to further modify the
.ini file to specify paths to where premet and spatial files are stored for MetGenC to use
as input files.

For granules suited to using the spatial extent defined for its collection,
a `collection_geometry_override = True` attribute/value pair can be added to the .ini file
(as long as it's a single bounding rectangle, and not two or more bounding rectangles).
Setting `collection_geometry_override = False` in the .ini file will make MetGenC look to the
science files or premet/spatial files for the granule-level spatial representation geometry
to use.

### Geometry Rules
|Granule Spatial Representation Geometry | Granule Spatial Representation Coordinate System (GSRCS) |
|--------------------------------------- | -------------------------------------------------------- |
| GPolygon (GPoly) | Geodetic |
| Bounding Rectangle (BR) | Cartesian |
| Points | Geodetic |

### Geometry Logic and Expectations Table
```
.spo = .spo file associated with each granule, used to directly define the vertices of a gPoly.
.spatial = .spatial file associated with each granule to define either: BR, Point, or the data footprint (i.e., the .spatial simply contains a listing of all coordinates parsed from the science file) for which MetGenC is to generate a detailed, encompassing GPoly.
```

| source | num points | GSRCS | error? | expected output | comments |
| ------ | ------------ | ---- | ------ | ------- | --- |
| .spo  |   any | cartesian | yes | | `.spo` inherently defines GPoly vertices; GPolys cannot be cartesian. |
| .spo   | <= 2 | geodetic | yes | | At least three points are required to define a GPoly. |
| .spo  | > 2 | geodetic | no | GPoly as described by `.spo` file contents. | |
| .spatial | 1 | cartesian | yes | | NSIDC data curators always associate a `GEODETIC` granule spatial representation with point data. |
| .spatial | 1 | geodetic | no | Point as defined by spatial file. | |
| .spatial | 2 | cartesian | no | BR as defined by spatial file. | |
| .spatial | >= 2 | geodetic | no | GPoly(s) calculated to enclose all points. | If `spatial_polygon_enabled=true` (default) and ≥3 points, uses optimized polygon generation with target coverage and vertex limits. |
| .spatial | > 2 | cartesian | yes | | There is no cartesian-associated geometry for GPolys. |
| science file (NSIDC/CF-compliant netCDF) | NA | cartesian | no | BR | min/max lon/lat points for BR expected to be included in global attributes. |
| science file (NSIDC/CF-compliant) | 1 or > 2 | geodetic | no | | Error if only two points. GPoly calculated from grid perimeter. |
| science file, non-NSIDC/CF-compliant netCDF or other format | NA | either | no | As specified by .ini file. | Configuration file must include a `spatial_dir` value (a path to the directory with valid `.spatial` or `.spo` files), or `collection_geometry_override = True` entry (which must be defined as a single point or a single bounding rectangle). |
| collection spatial metadata geometry = cartesian with one BR | NA | cartesian | no | BR as described in collection metadata. | |
| collection spatial metadata geometry = cartesian with one BR | NA | geodetic | yes | | Collection geometry and GSRCS must both be cartesian. |
| collection spatial metadata geometry = cartesian with two or more BR | NA | cartesian | yes | | Two-part bounding rectangle is not a valid granule-level geometry. |
| collection spatial metadata geometry specifying one or more points | NA | NA |  | | Not a known use case  |

## Running MetGenC: Its Commands In-depth

### help
Show MetGenC's help text:

        $ metgenc --help
        Usage: metgenc [OPTIONS] COMMAND [ARGS]...

          The metgenc utility allows users to create granule-level metadata, stage
          granule files and their associated metadata to Cumulus, and post CNM
          messages.

        Options:
          --help  Show this message and exit.

        Commands:
          info     Summarizes the contents of a configuration file.
          init     Populates a configuration file based on user input.
          process  Processes science files based on configuration file...
          validate Validates the contents of local JSON files.

* For detailed help on each command, run: `metgenc <command name> --help`:

        $ metgenc process --help

### init

The **init** command can be used to generate a metgenc configuration (i.e., .ini) file for
your data set, or edit an existing .ini file.
* You don't need to run this command if you already have an .ini file that you prefer
  to copy and edit manually (any text editor will work) to apply to the collection you're ingesting.
* If running metgenc init, the name of the new ini file you specify needs to include the `.ini` suffix.
```
metgenc init --help
Usage: metgenc init [OPTIONS]

  Populates a configuration file based on user input.

Options:
  -c, --config TEXT  Path to configuration file to create or replace
  --help             Show this message and exit
```

Example running **init**

    $ metgenc init -c ./init/<name of config file to create or modify>.ini

##### INI RULES:
* The .ini file's `checksum_type = SHA256` should never be edited
* The `kinesis_stream_name` and `staging_bucket_name` should never be edited
* `auth_id` and `version` must accurately reflect the collection's authID and versionID
* `log_dir` specifies the directory where metgenc log files will be written. Log files are named `metgenc-{config-name}-{timestamp}.log` where config-name is the base name of the .ini file and timestamp is in YYYYMMDD-HHMM format. The default log directory is `/share/logs/metgenc`, but this can be edited to write metgenc logs to a different existing, writable directory location.
* provider is a free text attribute where, for now, the version of metgenc being run should be documented
  * running `metgenc --version` will return the current version

#### Required and Optional Configuration Elements
Some attribute values may be read from the .ini file if the values
can't be gleaned from—or don't exist in—the science file(s), but whose
values are known for the data set. Use of these elements can be typical
for data sets comprising non-CF/non-NSIDC-compliant netCDF science files,
as well as non-netCDF data sets comprising .tif, .csv, .h5, etc. The element
values must be manually added to the .ini file, as none are prompted for
in the `metgenc init` functionality.

See this project's GitHub file, `fixtures/test.ini` for examples.

| .ini element           | .ini section | Attribute absent from netCDF file the .ini attribute stands in for | Attribute populated in UMMG | Note |
| -----------------------|-------------- | ------------------- | ---------------------------| ---- |
| time_start_regex       | Collection    | time_coverage_start | BeginningDateTime | 1    |
| time_coverage_duration | Collection    | time_coverage_end   | EndingDateTime | 2    |
| pixel_size             | Collection    | GeoTransform        | n/a | 3    |

R = Required for all non-netCDF file types (e.g., csv, .tif, .h5, etc) and netCDF files missing
    the global attribute specified

1. This regex attribute leverages a netCDF's file name containing a date to populate UMMG files'
   TemporalExtent field attribute, BeginningDateTime. Must match using the named group `(?P<time_coverage_start>)`.
   * This attribute is meant to be used with "nearly" compliant netCDF files, but not other file types
   (csv, tif, etc.) since these should rely on premet files containing temporal details for each file.

2. The time_coverage_duration attribute value specifies the duration to be applied to the `time_coverage_start` value
in order to generate EndingDateTime values in UMMG files; this value **is a constant**. It's only capable of appling the same
value to all time_start_regex value gleaned from files. The time_coverage_duration value must be a valid
[ISO duration value](https://en.wikipedia.org/wiki/ISO_8601#Durations).
   * This attribute is meant to be used only with "nearly" compliant _netCDF_ files--not any other file types
   since all other file types will rely on premet files to generate temporal details in output ummg metadata files.
Example:
```
time_start_regex = IRTIT3_(?P<time_coverage_start>\d{8})_
time_coverage_duration = P0DT23H59M59S
```

3. Rarely applicable for science files that aren't gridded netCDF (.txt, .csv, .jpg, .tif, etc.); this
value is a constant that will be applied to all granule-level metadata.

#### Granule and Browse regex

| .ini element | .ini section | Note |
| ------------- | ------------- | ---- |
| browse_regex  | Collection    | 1    |
| granule_regex | Collection    | 2    |
| reference_file_regex | Collection | 3 |

Note column:
1. The file name pattern identifying the browse file(s) accompanying single or multi-file granules. Granules
   with multiple associated browse files work fine with MetGenC! The default is `_brws`, change it to reflect
   the browse file names of the data delivered. This element is prompted for when running `metgenc init`.
2. The granule_regex is required for multi-file granules. It's what determines which files will be included 
   within the same granule based on it defining the common file name elements to be reflected in the ProducerGranuleId
   in the UMM-G file (= the granule name shown in EDSC).
   - This must result in a globally unique: product/name (in CNM), and Identifier (as the IdentifierType: ProducerGranuleId in UMM-G)
     generated for each granule.
   - As a general rule, include in the (?P<granuleid>) section of the granule_regex as much of the contiguous common elements of file names possible .  
   - This init element value must be added manually as it's **not** included in the `metgenc init` prompts.
4. The file name pattern identifying a single file for metgenc to reference as the primary
   file in a multi-file granule. This is required for processing multi-file granules. This element's value
   is prompted for when running `metgenc init`.
   * In the case of multi-file granules containing a CF-compliant netCDF science file and other supporting files
     like .tif, or .txt files, etc., specifying the netCDF file allows MetGenC to parse it as it would any other CF-compliant
     netCDF file, making it so operators won't need to supply premet/spatial files!!

##### INI File Example 1: Use of granule_regex for multi-file granules with no browse

Given the Config file Source and Collection contents:

```
[Source]
data_dir = /disks/sidads_staging/SNOWEX_metgen/SNEX_MCS_Lidar_metgen/data
premet_dir = /disks/sidads_staging/SNOWEX_metgen/SNEX_MCS_Lidar_metgen/premet
spatial_dir = /disks/sidads_staging/SNOWEX_metgen/SNEX_MCS_Lidar_metgen/spatial
collection_geometry_override = False
collection_temporal_override = False

[Collection]
auth_id = SNEX_MCS_Lidar
version = 1
provider = SnowEx
granule_regex = (SNEX_MCS_Lidar_)(?P<granuleid>\d{8})(?:_[-a-zA-Z0-9]+)(?:_V01\.0) 
reference_file_regex = _SD_
```
And two multi-file granules comprising the following files and their premet/spatial files named such that they reflect what will be the Granule ID:
```
SNEX_MCS_Lidar_20250404_DSM_V01.0.tif
SNEX_MCS_Lidar_20250404_DTM_V01.0.tif
SNEX_MCS_Lidar_20250404_SD_V01.0.tif
SNEX_MCS_Lidar_20250404_CHM_V01.0.tif
SNEX_MCS_Lidar_20221208.premet
SNEX_MCS_Lidar_20221208.spo

SNEX_MCS_Lidar_20221208_DSM_V01.0.tif
SNEX_MCS_Lidar_20221208_CHM_V01.0.tif
SNEX_MCS_Lidar_20221208_DTM_V01.0.tif
SNEX_MCS_Lidar_20221208_SD_V01.0.tif
SNEX_MCS_Lidar_20221208.premet
SNEX_MCS_Lidar_20221208.spo
```
The granule_regex sections:

- `(SNEX_MCS_Lidar_)` identifies a _Capturing Group_ which parses this constant expected to be included in each granule name, in this case it's the authID (NOTE: the versionID could/should also be made a capturing group. This particular data set sees ongoing ingest where originally the version ID was omitted from the multi-file granule names, so for consistency it's not included now and is made a non-capturing group, explained below.

- The _Named Capture Group granuleid_ `(?P<granuleid>\d{8})` matches the unique date contained in each file name to be included in each multi-file granule name, e.g., `IPFLT1B_20101226_085033_`.
  
- `(?:_[-a-zA-Z0-9]+)` and `(?:_V01\.0)` identify _Non-Capturing Groups_ comprising the variables and the version id named in each file. The Non-Capturing groups allow the regex to acknowledge the presence of these elements in individual file names, but lead them to be omitted from the multi-file granule name.

- Thus, SNEX_MCS_Lidar_ is combined with the granuleid capture group's unique date to form the producerGranuleId reflected for each granule in EDSC's Granules listing, and in this example, they're: `SNEX_MCS_Lidar_20250404` and `SNEX_MCS_Lidar_20221208`. These names are found in the CNM as the product/name value, and in the UMMG files as the Identifier value.

##### INI File Example 2: Single-file granule with good file names and no browse; omit browse_regex and granule_regex
This .ini file's \[Source\] and \[Collection\] contents apply to a single-file granule with no browse images:
```
[Source]
data_dir = /disks/sidads_staging/SNOWEX_metgen/SNEX23_CSU_GPR_metgen/data
premet_dir = /disks/sidads_staging/SNOWEX_metgen/SNEX23_CSU_GPR_metgen/premet
spatial_dir = /disks/sidads_staging/SNOWEX_metgen/SNEX23_CSU_GPR_metgen/spatial

[Collection]
auth_id = SNEX23_CSU_GPR
version = 1
provider = SnowEx
```
No regex are necessary since the file name will simply become the granule name.

##### INI File Example 3: Single-file granule with good file names and browse images; omit granule_regex
This .ini file's \[Source\] and \[Collection\] contents work for single-file granules with browse images:
```
[Source]
data_dir = ./data/0081

[Collection]
auth_id = NSIDC-0081
version = 2
provider = DPT
browse_regex = _F\d{2}
```
And two granules + their associated browse files and good granule names:
```
NSIDC0081_SEAICE_PS_N25km_20211101_v2.0.nc
NSIDC0081_SEAICE_PS_N25km_20211101_v2.0_F16.png
NSIDC0081_SEAICE_PS_N25km_20211101_v2.0_F17.png
NSIDC0081_SEAICE_PS_N25km_20211101_v2.0_F18.png
NSIDC0081_SEAICE_PS_S25km_20211102_v2.0.nc
NSIDC0081_SEAICE_PS_S25km_20211102_v2.0_F16.png
NSIDC0081_SEAICE_PS_S25km_20211102_v2.0_F17.png
NSIDC0081_SEAICE_PS_S25km_20211102_v2.0_F18.png
```
Only the browse_regex needs to be set to capture that which distinguishes the browse from the science files, in this case that's the presence of _F\d{2}, where _F\d{2} captures the number _F16, _F17, and _F18.

##### INI File Example 4: Use of `granule_regex` and `browse_regex` for single-file granules with interrupted file names
Given the .ini file's \[Source\] and \[Collection\] contents:
```
[Source]
data_dir = ./data/0081DUCk

[Collection]
auth_id = NSIDC-0081DUCk
version = 2
provider = DPT
browse_regex = _brws
granule_regex = (NSIDC0081_SEAICE_PS_)(?P<granuleid>[NS]{1}\d{2}km_\d{8})(_v2.0_)(?:F\d{2}_)?(DUCk)
```
And two granules + their associated browse files:
```
NSIDC0081_SEAICE_PS_N25km_20211101_v2.0_DUCk.nc
NSIDC0081_SEAICE_PS_N25km_20211101_v2.0_F16_DUCk_brws.png
NSIDC0081_SEAICE_PS_N25km_20211101_v2.0_F17_DUCk_brws.png
NSIDC0081_SEAICE_PS_N25km_20211101_v2.0_F18_DUCk_brws.png
NSIDC0081_SEAICE_PS_S25km_20211102_v2.0_DUCk.nc
NSIDC0081_SEAICE_PS_S25km_20211102_v2.0_F16_DUCk_brws.png
NSIDC0081_SEAICE_PS_S25km_20211102_v2.0_F17_DUCk_brws.png
NSIDC0081_SEAICE_PS_S25km_20211102_v2.0_F18_DUCk_brws.png
```

The browse_regex:
This simply identifies the part of the browse file name that distinguishes it as the browse from the science file, in this example: `browse_regex = _brws`.

The granule_regex sections:
In the case where a file name element interrupts what would be a string common to both the science and browse file names, a granule_regex is required to identify the granule name.
- `(NSIDC0081_SEAICE_PS_)`, `(_v2.0_)`, and `(DUCk)` identify the 1st, 3rd, and 4th (the last) _Capture Groups_. These are constants required to be present in each granules name: authID, version ID, and DUCk (the latter was only relevant for early CUAT testing). These are combined with the following...

- The _Named Capture Group granuleid_ `(?P<granuleid>[NS]{1}\d{2}km_\d{8})` matches the region, resolution, and date elements unique-yet-consistent within each file name (e.g., `N25km_20211101` and `S25km_20211102`), which are combined with the elements in the bullet above to form unique granule names. 

- `(?:F\d{2}_)?` matches the F16_, F17_, and F18_ strings in the browse file names as a _Non-capture Group_; these elements will be matched but **won't** be included in granule names.

- In summary: NSIDC0081_SEAICE_PS_, \_v2.0_, and DUCk are combined with the granuleid capture group element, `(?P<granuleid>[NS]{1}\d{2}km_\d{8})`, to form the producerGranuleId reflected for each granule, e.g., `NSIDC0081_SEAICE_PS_N25km_20211105_v2.0_DUCk.nc` and `NSIDC0081_SEAICE_PS_S25km_20211102_v2.0_DUCk.nc`. These are the names that will be shown for the granules in EDSC. They globally, uniquely distinguish granules in a specific collection from any other granules in any other collections in CUAT or CPROD. These names are found in the CNM as the `product`/`name` value, and the UMMG metadata file as the `Identifier value`.
  - If the granule_regex was omitted from the .ini file in this case, the cnm output would only define data and metadata files for ingest, the browse images would not be included!
  - Since metgenc validate doesn't check attribute values, no validation errors are thrown when this happens.
  - This hopefully is largely an example portraying a made-up edge case due to the way I'd added the _DUCk identifier to these files for early MetGenC testing!! But be aware of this if you find yourself dealing with complicated file names where the element meant to comprise the granule id are interrupted by other elements.
    
 The granuleid _Named Capture Group_ can **only define common** file name elements. When considering renaming files for a data set, keep in mind: the elements that vary within each file name comprising a multi-file granule must not fall within the granuleid _Named Capture Group_. Variable elements must be situated such that a _Non-Capturing Group_ can be used to account for them to create an appropriate granule ID, but a  _Non-Capturing Group_ can't be nestled within the granuleid _Named Capture Group_.

##### INI File Example 5: Use of `granule_regex` and `browse_regex` for multi-file granules with variables in file names
ini file \[Source\] and \[Collection\] contents:
```
[Source]
data_dir = /disks/sidads_staging/SNOWEX_metgen/SNEX23_SD_TLI_metgen/data
collection_geometry_override = True
collection_temporal_override = True

[Collection]
auth_id = SNEX23_SD_TLI
version = 1
provider = SnowEx
browse_regex = _brws
granule_regex = (SNEX23_SD_TLI_)(?:[a-z]+)_(?P<granuleid>\d{8}-\d{8}_)(V01\.0)
reference_file_regex = (SNEX23_SD_TLI_)(snowdepth_\d{8}-\d{8}_)(V01\.0)
```
and file names:
```
SNEX17_SD_TLI_snowdepth_20161001-20170601_V01.0.csv
SNEX17_SD_TLI_polemetadata_20161001-20170601_V01.0.csv
SNEX17_SD_TLI_labels_20161001-20170601_V01.0.csv
SNEX17_SD_TLI_image_20161001-20170601_V01.0_brws.png
```
 - (SNEX23_SD_TLI_) and (V01\.0) are _Capture Groups_
 - (?:[a-z]+) is the _Non-Capturing Group_ to omit the variables (snowdepth, polemetadata, etc.) from the multi-file granule's granule ID
 - (?P<granuleid>\d{8}-\d{8}_) is the _granuleid_ _Named Capture Group_ to include the date in the granule ID
The resulting multi-file granule ID is: `SNEX23_SD_TLI_20221014-20240601_V01.0`. This collection didn't require premet/spatial files as it was set to use the collection's temporal extent, and its geometry as the spatial representation. FYI: _Had premet/spatial files been required_, they would have needed to be named `SNEX23_SD_TLI_20221014-20240601_V01.0.premet` and `SNEX23_SD_TLI_20221014-20240601_V01.0.spatial <or .spo>`.


#### Using Premet and Spatial files
The following two .ini elements can be added to the .ini file to define paths
to the directories containing `premet` and `spatial` files. The paths must define
two distinct directories which must also be distinct from the data directory. 
The user will be prompted for these values when running `metgenc init` (but are optional
elements in the .ini file).
| .ini element | .ini section |
| ------------- | ------------- |
| premet_dir    | Source        |
| spatial_dir   | Source        |

- The spatial_dir is used to define a path to the directory containing either .spatial or .spo files.
- The composition of .spatial/.spo and .premet files and their naming convention remains exactly
   as it was for their use with SIPSMetgen (as described here: https://nsidc.org/sites/default/files/documents/other/guidelines-preliminary-metadata-creation-and-data-product-delivery.pdf).
  - This was done to avoid changing existing ops and/or data producer workflows/scripts.
- Reminder for premets: there should be a compelling reason (such as a need to preserve granule-level
  metadata continuity for an existing collection) from the pub team in order to include more
  attributes than just begin/end date/time. Most, if not all, new data sets requiring
  premets should see them include only begin/end date/time.
- At the moment with the production metgenc vm running **metgenc version 1.12.0**, when .spo files are used
  for a data set, the .ini file needs to include a [Spatial] section defininig `spatial_polygon_enabled = false`
  so that the vertices defined are used directly (instead of accidentally interpreted by MetGenC as a data set
  footprint around which a gpolygon needs to be generated). 
  e.g.,
```
[Spatial]
spatial_polygon_enabled = false
```
(Note: A fix has been implemented in MetGenC version 1.13.0rc0; once version 1.13.0 is released and running
on the production metgenc vm, the .spo issue will be a thing of the past).
 
#### Setting Collection Spatial Extent as Granule Spatial Extent
In cases of data sets where granule spatial information is not available
by interrogating the data or via `spatial` or `.spo` files, the operator
may set a flag to force the metadata representing each granule's spatial
extents to be set to that of the collection. The user will be prompted
for the `collection_geometry_override` value when running `metgenc init`.
The default value is `False`; setting it to `True` signals MetGenC to
use the collection's spatial extent for each granule.
| .ini element                | .ini section |
| ---------------------------- | ------------- |
| collection_geometry_override | Source        |

#### Setting Collection Temporal Extent as Granule Temporal Extent
RARELY APPLICABLE (if ever)!! An operator may set an .ini flag to indicate
that a collection's temporal extent should be used to populate every granule
via granule-level UMMG json to be the same TemporalExtent (SingleDateTime or
BeginningDateTime and EndingDateTime) as what's defined for the collection.
In other words, every granule in a collection would display the same start
and end times in EDSC. In most collections, this is likely ill-advised use case.
The operator will be prompted for a `collection_temporal_override`
value when running `metgenc init`. The default value is `False` and should likely
always be accepted; setting it to `True` is what would signal MetGenC to set each
granule to the collection's TemporalExtent.

| .ini element                 | .ini section |
| ----------------------------- | --------------|
| collection_temporal_override  | Source        |

#### Spatial Polygon Generation
MetGenC includes optimized polygon generation capabilities for creating spatial coverage polygons from point data, particularly useful for LIDAR flightline data.

When a granule has an associated `.spatial` file containing geodetic point data (≥3 points), MetGenC will automatically generate an optimized polygon to enclose the data points instead of using the basic point-to-point polygon method. This results in more accurate spatial coverage with fewer vertices.

**This feature, while optional, is always enabled by default in MetGenC**. 
- To disable it entirely, edit the .ini file, add a \[Spatial\] section if necessary, and add the line `spatial_polygon_enabled = false`. **CURRENTLY RECOMMENDED TO SET `spatial_polygon_enabled = false` WHENEVER .SPO FILES ARE USED.**
- When `spatial_polygon_enabled = true` (either by default or when set as such in the .ini file) the other parameters listed below can be added to
  and edited in the .ini file. For the most part, the values shouldn't need to be altered! However, if ingest fails due to GPolygonSpatial errors,
  the first attribute to add to or edit in the .ini file should be `spatial_polygon_cartesian_tolerance` by decreasing its coordinate precision
  (e.g., .0001 => .01) which will increase the distance between gpolygon vertices, expanding the spatial extent.

**Configuration Parameters:**

| .ini section | .ini element                    | Type    | Default | Description |
| ------------- | -------------------------------- | ------- | ------- | ----------- |
| Spatial       | spatial_polygon_enabled          | boolean | true    | Enable/disable polygon generation for .spatial files |
| Spatial       | spatial_polygon_target_coverage  | float   | 0.98    | Target data coverage percentage (0.80-1.0) |
| Spatial       | spatial_polygon_max_vertices     | integer | 100     | Maximum vertices in generated polygon (10-1000) |
| Spatial       | spatial_polygon_cartesian_tolerance | float | 0.0001  | Minimum distance between polygon points in degrees (0.00001-0.01) |

##### Example Spatial Polygon Generation Configuration
Example showing content added to an .ini file, having edited the CMR default vertex tolerance
(distance between two vertices) to decrease the precision of the GPoly coordinate pairs listed
in the UMMG json files MetGenC generates:
```ini
[Spatial]
spatial_polygon_enabled = true
spatial_polygon_target_coverage = 0.98
spatial_polygon_max_vertices = 100
spatial_polygon_cartesian_tolerance = .01
```
Example showing the key pair added to an .ini file to disable spatial polygon generation:
```ini
[Spatial]
spatial_polygon_enabled = false
```

**When Polygon Generation is Applied:**
- ✅ Granule has a `.spatial` file with ≥3 geodetic points
- ✅ `spatial_polygon_enabled = true` (default)
- ✅ Granule spatial representation is `GEODETIC`

**When Original Behavior is Used:**
- ❌ No `.spatial` file present (data from other sources)
- ❌ `spatial_polygon_enabled = false`
- ❌ Granule spatial representation is `CARTESIAN`
- ❌ Insufficient points (<3) for polygon generation
- ❌ Polygon generation fails (automatic fallback)

**Tolerance Requirements:**
The `spatial_polygon_cartesian_tolerance` parameter ensures that generated polygons meet NASA CMR validation requirements. The CMR system requires that each point in a polygon must have a unique spatial location - if two points are closer than the tolerance threshold in both latitude and longitude, they are considered the same point and the polygon becomes invalid. MetGenC automatically filters points during polygon generation to ensure this requirement is met.

This enhancement is backward compatible - existing workflows continue unchanged, and polygon generation only activates for appropriate `.spatial` file scenarios.

##### Geospatial Bounds Configuration

MetGenC can extract polygon vertices directly from the `geospatial_bounds`
netCDF attribute when it contains a WKT POLYGON string. This extracts all
polygon vertices as individual points, providing an alternative to the default
of using spatial coordinate values to generate a polygon.
 **If no `geospatial_bounds_crs` attribute exists, the
`geospatial_bounds` value is assumed to represent points in EPSG:4326.**

**Example Configuration:**
```ini
[Spatial]
prefer_geospatial_bounds = true
```

**When Geospatial Bounds Extraction is Applied:**
- ✅ Granule spatial representation is `GEODETIC`
- ✅ `prefer_geospatial_bounds = true` in .ini file
- ✅ NetCDF file contains valid `geospatial_bounds` global attribute with WKT POLYGON

---

### info

The **info** command can be used to display the information within the configuration file as well as MetGenC system default values for data ingest.

```
metgenc info --help
Usage: metgenc info [OPTIONS]

  Summarizes the contents of a configuration file.

Options:
  -c, --config TEXT  Path to configuration file to display  [required]
  --help             Show this message and exit.
```

#### Example running info

```
metgenc info -c /share/apps/metgenc/SNEX23_CSU_GPR/init/SNEX23_CSU_GPR.ini
                   __
   ____ ___  ___  / /_____ ____  ____  _____
  / __ `__ \/ _ \/ __/ __ `/ _ \/ __ \/ ___/
 / / / / / /  __/ /_/ /_/ /  __/ / / / /__
/_/ /_/ /_/\___/\__/\__, /\___/_/ /_/\___/
                   /____/
Using configuration:
  + environment: uat
  + data_dir: /disks/sidads_staging/SNOWEX_metgen/SNEX23_CSU_GPR_metgen/data
  + auth_id: SNEX23_CSU_GPR
  + version: 1
  + provider: SnowEx
  + local_output_dir: /share/apps/metgenc/SNEX23_CSU_GPR/output
  + ummg_dir: ummg
  + kinesis_stream_name: nsidc-cumulus-uat-external_notification
  + staging_bucket_name: nsidc-cumulus-uat-ingest-staging
  + write_cnm_file: True
  + overwrite_ummg: True
  + checksum_type: SHA256
  + number: 1000000
  + dry_run: False
  + premet_dir: /disks/sidads_staging/SNOWEX_metgen/SNEX23_CSU_GPR_metgen/premet
  + spatial_dir: /disks/sidads_staging/SNOWEX_metgen/SNEX23_CSU_GPR_metgen/spatial
  + collection_geometry_override: False
  + collection_temporal_override: False
  + time_start_regex: None
  + time_coverage_duration: None
  + pixel_size: None
  + browse_regex: _brws
  + granule_regex: None
  + reference_file_regex: None
  + spatial_polygon_enabled: False
  + spatial_polygon_target_coverage: 0.98
  + spatial_polygon_max_vertices: 100
  + spatial_polygon_cartesian_tolerance: 0.0001
  + prefer_geospatial_bounds: False
  + log_dir: /share/logs/metgenc
  + name: SNEX23_CSU_GPR
```
---

### process
```
metgenc process --help

Usage: metgenc process [OPTIONS]

  Processes science files based on configuration file contents.

Options:
  -c, --config TEXT   Path to configuration file  [required]
  -d, --dry-run       Don't stage files on S3 or publish messages to Kinesis
  -e, --env TEXT      environment  [default: uat]  #note: this can be set to either `uat` or `prod`
  -n, --number count  Process at most 'count' granules.
  -wc, --write-cnm    Write CNM messages to files.
  -o, --overwrite     Overwrite existing UMM-G files.
  --help              Show this message and exit.
```
The **process** command can be run either with or without specifying the `-d` / `--dry-run` option.
* When the dry run option is specified _and_ the `-wc` / `--write-cnm` option is invoked, or your config
file contains `write_cnm_file = true` (instead of `= false`), CNM will be written locally to the output/cnm
directory (**operator is responsible for creating the output and ummg, cnm subdirectories for each collection**). This promotes operators having the ability to validate and visually QC their content before ingesting a collection.
* When run without the dry run option, metgenc will transfer CNM to AWS, kicking off end-to-end ingest of
data and UMM-G files.

#### Examples running process
The following is an example of using the dry run option (-d) to generate UMM-G and write CNM as files (-wc) for three granules (-n 3):

    $ metgenc process -c ./init/test.ini -d -n 3 -wc

This next example would run end-to-end ingest of all granules (assuming < 1000000 granules) in the data directory specified in the test.ini config file
and their UMM-G files into the CUAT environment:

    $ metgenc process -c ./init/test.ini -e <uat or prod>
Note: Before running **process** without the dry run option, **post Slack messages to NSIDC's `#Cumulus` and `cloud-ingest-ops`
channels, and post a quick "done" note when you're done ingest testing as a courtesy to Cumulus devs and ops folks**


#### Troubleshooting metgenc process
* MetGenC processing, `metgenc process -d -c init/xxxxx.ini`, must be run at the ~/metgenc level in the
  vm's virtual environment, e.g., `vagrant@vmpolark2:~/metgenc$`. If you run it in the data/, or init/, or any other
  directory, you'll see errors like:
```
The configuration is invalid:
  * The data_dir does not exist.
  * The premet_dir does not exist.
  * The spatial_dir does not exist.
  * The local_output_dir does not exist.
```
* If running `metgenc process` fails for other reasons, check for an error message in the metgenc log. This is written by default to/as (/share/logs/metgenc/`metgenc-{config-name}-{timestamp}.log`).
  * The metgenc.log will spell out the reason for the error for the operator, so the .ini file or paths pointed to in the .ini file can be spiffed up.

* If running metgenc process without the -d / --dry-run option leads to the following warning:
```
  The configuration is invalid:
    The kinesis stream does not exist.
    The staging bucket does not exist.
```
  It's almost certainly indicating that you've not sourced the credentials required (cumulus-uat, cumulus-prod) for the environment you're telling MetGenC to process in.

* If metgenc reports "Successful   : False" for a specific granule, you can copy the UUID (or, just the last alphanumeric block after the dash is adequate), and then grep the metgenc log for that processing run for that id specifying only 46 lines after the id to be returned. That'll show you the log details just for that granule!
```
  e.g., grep -A 46 43eae1561cba metgenc.log
```
  
---

### validate

The **validate** command lets you review the JSON CNM or UMM-G output files created by
running `process`.

```
metgenc validate --help

Usage: metgenc validate [OPTIONS]

  Validates the contents of local JSON files.

Options:
  -c, --config TEXT  Path to configuration file  [required]
  -t, --type TEXT    JSON content type  [default: cnm]
  --help             Show this message and exit.
```

#### Example running validate

    $ metgenc validate -c init/modscg.ini -t ummg (adding the -t ummg option will validate all UMM-G files; -t cnm will validate all CNM that have been written locally)
    $ metgenc validate -c init/modscg.ini (without the -t option specified, just all locally written CNM will be validated)

running the following is an alternate way to validate ummg and cnm json files, but can only be run on one file at a time:

    $ check-jsonschema --schemafile <path to schema file> <path to CNM or UMM-G file to check>

If running `metgenc validate` fails, check the metgenc.log for an error message to begin troubleshooting.   

### Pretty-print a json file in your shell
Handy tip: While not a MetGenC command, a handy way to show a file's contents without having
to wade through unformatted json chaos is to run:
`cat <UMM-G or CNM file name> | jq `

e.g., running `cat /share/apps/metgenc/SNEX23_CSU_GPR/output/cnm/SNEX23_CSU_GPR_FLCF_20230307_20230316_v01.csv.cnm.json | jq`
will pretty-print the contents of this cnm.json file in the comfort of your own shell!

## For Developers
### Contributing

#### Requirements

* [Python](https://www.python.org/) v3.12+
* [Poetry](https://python-poetry.org/docs/#installing-with-the-official-installer)

You can install [Poetry](https://python-poetry.org/) either by using the [official
installer](https://python-poetry.org/docs/#installing-with-the-official-installer)
if you’re comfortable following the instructions, or by using a package
manager (like Homebrew) if this is more familiar to you. When successfully
installed, you should be able to run:

    $ poetry --version
    Poetry (version 1.8.3)

#### Installing Dependencies

* Use Poetry to create and activate a virtual environment

      $ poetry shell

* Install dependencies

      $ poetry install

#### Run tests

    $ poetry run pytest

#### Run tests when source changes
This uses [pytest-watcher](https://github.com/olzhasar/pytest-watcher)

    $ poetry run ptw . --now --clear

#### Running the linter for code style issues

    $ poetry run ruff check

[The `ruff` tool](https://docs.astral.sh/ruff/linter/) will check
the source code for conformity with various style rules. Some of
these can be fixed by `ruff` itself, and if so, the output will
describe how to automatically fix these issues.

The CI/CD pipeline will run these checks whenever new commits are
pushed to GitHub, and the results will be available in the GitHub
Actions output.

#### Running the code formatter

    $ poetry run ruff format

[The `ruff` tool](https://docs.astral.sh/ruff/formatter/) will check
the source code for conformity with source code formatting rules. It
will also fix any issues it finds and leave the changes uncommitted
so you can review the changes prior to adding them to the codebase.

As with the linter, the CI/CD pipeline will run the formatter when
commits are pushed to GitHub.

#### Ruff integration with your editor

Rather than running `ruff` manually from the commandline, it can be
integrated with the editor of your choice. See the
[ruff editor integration](https://docs.astral.sh/ruff/editors/) guide.


#### Releasing

* Update `CHANGELOG.md` according to its representation of the current version:
  * If the current "version" in `CHANGELOG.md` is `UNRELEASED`, add an
    entry describing your new changes to the existing change summary list.

  * If the current version in `CHANGELOG.md` is **not** a release candidate,
    add a new line at the top of `CHANGELOG.md` with a "version" consisting of
    the string literal `UNRELEASED` (no quotes surrounding the string).  It will
    be replaced with the release candidate form of an actual version number
    after the `major`, `minor`, or `patch` version is bumped (see below). Add a
    list summarizing the changes (thus far) in this new version below the
    `UNRELEASED` version entry.

  * If the current version in `CHANGELOG.md`  **is** a release candidate, add
    an entry describing your new changes to the existing change summary list for
    this release candidate version. The release candidate version will be
    automatically updated when the `rc` version is bumped (see below).

* Commit `CHANGELOG.md` so the working directory is clean.

* Show the current version and the possible next versions:

        $ bump-my-version show-bump
        1.4.0 ── bump ─┬─ major ─── 2.0.0rc0
                       ├─ minor ─── 1.5.0rc0
                       ├─ patch ─── 1.4.1rc0
                       ├─ release ─ invalid: The part has already the maximum value among ['rc', 'release'] and cannot be bumped.
                       ╰─ rc ────── 1.4.0release1

* If the currently released version of `metgenc` is not a release candidate
  and the goal is to start work on a new version, the first step is to create a
  pre-release version. As an example, if the current version is `1.4.0` and
  you'd like to release `1.5.0`, first create a pre-release for testing:

        $ bump-my-version bump minor

  Now the project version will be `1.5.0rc0` -- Release Candidate 0. As testing
  for this release-candidate proceeds, you can create more release-candidates by:

        $ bump-my-version bump rc

  And the version will now be `1.5.0rc1`. You can create as many release candidates as needed.

* When you are ready to do a final release, you can:

        $ bump-my-version bump release

  Which will update the version to `1.5.0`. After doing any kind of release, you will see
  the latest commit and tag by looking at `git log`. You can then push these to GitHub
  (`git push --follow-tags`) to trigger the CI/CD workflow.

* On the [GitHub repository](https://github.com/nsidc/granule-metgen), click
  'Releases' and follow the steps documented on the
  [GitHub Releases page](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository#creating-a-release).
  Draft a new Release using the version tag created above. By default, the 'Set
  as the latest release' checkbox will be selected. To publish a pre-release
  from a release candidate version, be sure to select the 'Set as a pre-release'
  checkbox. After you have published the (pre-)release in GitHub, the MetGenC
  Publish GHA workflow will be started.  Check that the workflow succeeds on the
  [MetGenC Actions page](https://github.com/nsidc/granule-metgen/actions),
  and verify that the
  [new MetGenC (pre-)release is available on PyPI](https://pypi.org/project/nsidc-metgenc/).

## Credit

This content was developed by the National Snow and Ice Data Center with funding from
multiple sources.
