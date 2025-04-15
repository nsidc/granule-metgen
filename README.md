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

## Requirements

To use the `nsidc-metgen` command-line tool, `metgenc`, you must first have
Python version 3.12 installed. To determine the version of Python you have, run
this at the command-line:

    $ python --version

or

    $ python3 --version

## Installing MetGenC

MetGenC can be installed from [PyPI](https://pypi.org/). First, create a
Python virtual environment (venv) in a directory of your choice, then activate it. To do this...

On a Mac, open Terminal and run:

    $ python -m venv /Users/afitzger/metgenc (i.e. provide the path and name of the venv where you'll house MetGenC)
    $ source ~/metgenc/bin/activate (i.e., activates your newly created metgenc venv)

On a Windows machine, open a command prompt, navigate to the desired project directory in which to create your venv, then run:

    > python -m venv metgenc (i.e., in this case, a venv named "metgenc" is created within the current directory)
    > .\<path to venv>\Scripts\activate (i.e., activates your newly created metgenc venv) 

Now, whatever your OS, install MetGenC into the virtual environment using `pip`:

    $ pip install nsidc-metgenc

## AWS Credentials

In order to process science data and stage it for Cumulus, you must first create & setup your AWS
credentials. Two options for doing this are:

### Option 1: Manually Creating Configuration Files

First, create a directory in your user's home directory to store the AWS configuration:

    $ mkdir -p ~/.aws

In the `~/.aws` directory, create a file named `config` with the contents:

    [default]
    region = us-west-2
    output = json

In the `~/.aws` directory, create a file named `credentials` with the contents:

    [default]
    aws_access_key_id = TBD
    aws_secret_access_key = TBD

The examples above create a [default AWS profile](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html#cli-configure-files-format-profile).
If you require access to multiple AWS accounts, each with their own configuration--for example, different accounts for pre-production vs. production--you
can use the [AWS CLI 'profile' feature to manage settings for each account](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html#cli-configure-files-using-profiles).


Finally, restrict the permissions of the directory and files:

    $ chmod -R go-rwx ~/.aws

When you've obtained the AWS key pair ([covered here]([https://nsidc.atlassian.net/l/cp/YYj1gGsp])),
edit your newly created `~/.aws/credentials` file and replace `TBD` with the public and secret
key values.

### Option 2: Using the AWS CLI to Create Configuration Files

You may install (or already have it installed) the AWS Command Line Interface on the
machine where you are running the tool. Follow the
[AWS CLI Install instructions](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
for the platform on which you are running.

Once you have the AWS CLI, you can use it to create the `~/.aws` directory and the
`config` and `credentials` files:

    $ aws configure

You will be prompted to enter your AWS public access and secret key values, along with
the AWS region and CLI output format. The AWS CLI will create and populate the directory
and files with your values.

## CMR Authentication and use of Collection Metadata

MetGenC will attempt to authenticate with Earthdata using credentials retrieved
from the environment and retrieve collection metadata. If authentication fails,
collection metadata will not be available to compensate for metadata elements 
missing from `ini` files or the data files themselves.

Export the following variables to your environment before you kick off MetGenC:

    $ export EARTHDATA_USERNAME=your-EDL-user-name
    $ export EARTHDATA_PASSWORD=your-EDL-password

If you have a different user name and password for the UAT and production
environments, be sure to set the values appropriate for the environment option
passed to `metgenc process`.

If collection metadata are unavailable, either due to an authentication failure
or because the collection information doesn't yet exist in CMR, MetGenC will
continue processing with the information available from the `ini` file and the
data files.

## Before Running MetGenC: Tips and Assumptions

* Verify the application version:

        $ metgenc --version
        metgenc, version 1.3.0

* Show the help text:

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
          process  Processes science data files based on configuration file...
          validate Validates the contents of local JSON files.

* For detailed help on each command, run: metgenc <command> --help, for example:

        $ metgenc process --help
        
### Assumptions for netCDF files for MetGenC

* NetCDF files have an extension of `.nc` (per CF conventions).
* Projected spatial information is available in coordinate variables having
  a `standard_name` attribute value of `projection_x_coordinate` or
  `projection_y_coordinate` attribute.
* (y[0],x[0]) represents the upper left corner of the spatial coverage.
* Spatial coordinate values represent the center of the area covered by a measurement.
* Only one coordinate system is used by all data variables in all data files
  (i.e. only one grid mapping variable is present in a file, and the content of
  that variable is the same in every data file).

### MetGenC `ini` File Assumtions
* If a `pixel_size` value is present in the `ini` file, its units are assumed to be
  the same as the units of the spatial coordinate variables.
* Date/time strings can be parsed using `datetime.fromisoformat`
* Checksums are all SHA256
  
### Reference links

* https://wiki.esipfed.org/Attribute_Convention_for_Data_Discovery_1-3
* https://cfconventions.org/Data/cf-conventions/cf-conventions-1.11/cf-conventions.html

### NetCDF Attributes Used to Populate the UMM-G files generated by MetGenC

- **Required** required
- **RequiredC** conditionally required
- **R+** highly or strongly recommended
- **R** recommended
- **S** suggested

| Attribute in use (location)   | ACDD | CF Conventions | NSIDC Guidelines | Note    |
| ----------------------------- | ---- | -------------- | ---------------- | ------- |
| date_modified (global)        | S    |                | R                | 1, OC   |
| time_coverage_start (global)  | R    |                | R                | 2, OC, P   |
| time_coverage_end (global)    | R    |                | R                | 2, OC, P   |
| grid_mapping_name (variable)  |      | RequiredC      | R+               | 3       |
| crs_wkt (variable with `grid_mapping_name` attribute)      |  |  | R     | 4       |
| GeoTransform (variable with `grid_mapping_name` attribute) |  |  | R     | 5, OC   |
| standard_name, `projection_x_coordinate` (variable) |  | RequiredC  |    | 6       |
| standard_name, `projection_y_coordinate` (variable) |  | RequiredC  |    | 7       |

Notes:
OC = Attributes (or elements of them) that may be represented in the `ini` file.
P = Attributes that may be specified in a `premet` file; a `premet_dir` directory must be defined in the `ini` file.
See [Optional Configuration Elements](#optional-configuration-elements)

1. Used to populate the production date and time values in UMM-G output.
2. Used to populate the time begin and end UMM-G values.
3. A grid mapping variable is required if the horizontal spatial coordinates are not
   longitude and latitude and the intent of the data provider is to geolocate
   the data. `grid_mapping` and `grid_mapping_name` allow programmatic identification of
   the variable holding information about the horizontal coordinate reference system.
4. The `crs_wkt` ("well known text") value is handed to the
   `CRS` and `Transformer` modules in `pyproj` to conveniently deal
   with the reprojection of (y,x) values to EPSG 4326 (lon, lat) values.
5. The `GeoTransform` value provides the pixel size per data value, which is then used
   to calculate the padding added to x and y values to create a GPolygon enclosing all
   of the data.
6. The values of the coordinate variable identified by the `standard_name` attribute
   with a value of `projection_x_coordinate` are reprojected and thinned to create a
   GPolygon, bounding box, etc.
7. The values of the coordinate variable identified by the `standard_name` attribute
   with a value of `projection_y_coordinate` are reprojected and thinned to create a
   GPolygon, bounding box, etc.
   
| Attributes not currently used | ACDD | CF Conventions | NSIDC Guidelines |
| ----------------------------- | ---- | -------------- | ---------------- |
| Conventions (global)          | R+   | Required       | R                |
| standard_name (data variable) | R+   | R+             |                  |
| grid_mapping (data variable)  |      | RequiredC      | R+               |
| axis (variable)               |      | R              |                  |
| geospatial_bounds (global)    | R    |                | R                |
| geospatial_bounds_crs (global)| R    |                | R                |
| geospatial_lat_min (global)   | R    |                | R                |
| geospatial_lat_max (global)   | R    |                | R                |
| geospatial_lat_units (global) | R    |                | R                |
| geospatial_lon_min (global)   | R    |                | R                |
| geospatial_lon_max (global)   | R    |                | R                |
| geospatial_lon_units (global) | R    |                | R                |

## Running MetGenC: Its Commands In-depth

### init

The **init** command can be used to generate a metgenc configuration (i.e., `.ini`) file for
your data set, or edit an existing .ini file. 
* You can skip this step if you've already made an .ini file and prefer editing it
  manually (any text editor will work).
* An existing configuration file can also be copied and renamed to be used for a different
  data set, just be sure to update the data_dir, auth_id, version, and provider!
* Make sure to confirm the configuration file's checksum_type is set to SHA256.

```
metgenc init --help
Usage: metgenc init [OPTIONS]

  Populates a configuration file based on user input.

Options:
  -c, --config TEXT  Path to configuration file to create or replace
  --help             Show this message and exit
```

Example running **init**

    $ metgenc init -c ./init/<name of the config file you’d like to create or modify>.ini

#### Optional Configuration Elements

Some attribute values may be read from the `ini` file if they don't exist
in the granule data file(s). This approach assumes the attribute values
are the same for all granules. These values must be manually added to the
`ini` file; they are not included in the `metgenc init` functionality.

See the file `fixtures/test.ini` for examples.

| (NetCDF) Attribute  | `ini` section | `ini` element | Note |
| --------------------|-------------- | ------------- | ----- |
| date_modified       | Collection    | date_modified |       |
| time_coverage_start | Collection    | time_start_regex | 1  |
| time_coverage_end   | Collection    | time_coverage_duration | 2 |
| GeoTransform        | Collection    | pixel_size    |        |


1. Matched against file name to determine time coverage start value. Must match using
the named group `(?P<time_coverage_start>)`.

2. Duration value applied to `time_coverage_start` to determine `time_coverage_end`.  Must be a valid [ISO duration value](https://en.wikipedia.org/wiki/ISO_8601#Durations).

Two additional `ini` values are used to identify browse files and the file name
pattern (if any) that indicates which file(s) should be grouped together as a
single granule (or browse file(s) associated with a granule).

| `ini` section | `ini` element | Note |
| ------------- | ------------- | ---- |
| Collection    | browse_regex  | 1    |
| Collection    | granule_regex | 2    |

1. The file name pattern identifying a browse file. Defaults to `_brws`. Included in the
 `metgenc init` prompts.
2. The file name pattern identifying related files. Must  capture all text
 comprising the granule name in UMM-G and CNM output, and must provide a match
 using the named group `(?P<granuleid>)`. This value must be added manually; it
 is **not** included in the `metgenc init` prompts.

Paths to the directories containing `premet` and `spatial` files are also 
included in the `ini` file. The user will be prompted for these values when running
`metgenc init`.

| `ini` section | `ini` element |
| ------------- | ------------- |
| Collection    | premet_dir    |
| Collection    | spatial_dir   |

##### Example `granule_regex` application

Given the `granule_regex` below:

```
granule_regex = (NSIDC0081_SEAICE_PS_)(?P<granuleid>[NS]{1}\d{2}km_\d{8})(_v2.0_)(?:F\d{2}_)?(DUCk)
```

And two granules with associated browse files:

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

- `(?:F\d{2}_)?` will match the `F16_`, `F17_` and `F18_` strings in the browse
file names, but the match will not be captured due to to the `?:` elements and will
not appear in the granule name recorded in the UMM-G and CNM output.
- `N25km_20211101` and `S25km_20211102` will match the named capture group `granuleid`.
Each of those strings uniquely identify all files associated with a given granule.
- `NSIDC0081_SEAICE_PS_`, `_v2.0_` and `DUCk` will be combined with the `granuleid`
text to form the granule name recorded in the UMM-G and CNM output (in the case of
single data file granules, the file extension will be added to the granule name).


---

### info

The **info** command can be used to display the information within the configuration file.

```
metgenc info --help
Usage: metgenc info [OPTIONS]

  Summarizes the contents of a configuration file.

Options:
  -c, --config TEXT  Path to configuration file to display  [required]
  --help             Show this message and exit.
```

Example running **info**

    $ metgenc info --config example/modscg.ini

---

### process

The **process** command is used either to generate UMM-G and CNM files locally to give
you a chance to review them before ingesting them (with either `-d`, `--dry-run` option), or to
kick off end-to-end ingest of data and UMM-G files to Cumulus UAT. 

```
metgenc process --help

Usage: metgenc process [OPTIONS]

  Processes science data files based on configuration file contents.

Options:
  -c, --config TEXT   Path to configuration file  [required]
  -d, --dry-run       Don't stage files on S3 or publish messages to Kinesis
  -e, --env TEXT      environment  [default: uat]
  -n, --number count  Process at most 'count' granules.
  -wc, --write-cnm    Write CNM messages to files.
  -o, --overwrite     Overwrite existing UMM-G files.
  --help              Show this message and exit.
```

Notes: 
* Before running **process**, remember to source your AWS profile by running
  `$ source metgenc-env.sh cumulus-uat` — in this case `cumulus-uat` is the profile name I specified
  in my AWS credential and config files; use whatever profile name you've specified for `uat` in your 
  config and credential files!
* If you can't remember whether you've sourced your AWS profile yet in a given MetGenC session,
  there's no harm in sourcing it again. Once run though, you'll be all set for however long
  you're working in your active venv.
* Before running end-to-end ingest, as a courtesy send a Slack message to NSIDC's `#Cumulus`
  channel so if they happen to notice activity, they know it's your handiwork.
  
Examples running **process**

The following is an example of using the dry run option for three granules:

    $ metgenc process -c ./init/test.ini -e uat  -d -n 3

This next example runs an end-to-end ingest of granules and their ummg files into 
Cumulus UAT:

    $ metgenc process -c ./init/test.ini -e uat

---

### validate

The **validate** command lets you review the JSON cnm or ummg output files created by
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

Example running **validate**

    $ metgenc validate -c example/modscg.ini -t ummg

The package `check-jsonschema` is also installed by MetGenC and can be used to validate a single file:

    $ check-jsonschema --schemafile <path to schema file> <path to cnm file>


## Troubleshooting

If you run `$ metgenc process -c ./init/test.ini` to test end-to-end ingest, but you get a flurry of errors, run: 

    source metgenc-env.sh cumulus-uat

Replacing `cumulus-uat` (if necessary) with the name of the AWS credentials
profile you set up for the Cumulus `uat` environment. If you've been running
other metgenc commands successfully (even `metgenc process` but with the
--dry-run option), having forgotten to set up communications between MetGenC and
AWS is very easy to do, but thankfully, very easy to resolve.

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

#### Run tests when source changes (uses [pytest-watcher](https://github.com/olzhasar/pytest-watcher)):

    $ poetry run ptw . --now --clear

#### Running the linter for code style issues:

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
