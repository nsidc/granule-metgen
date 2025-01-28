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

## Assumptions

* Checksums are all SHA256
* NetCDF files have an extension of `.nc` (required by CF conventions)
* (x[0],y[0]) represents the upper left corner of the spatial coverage.
* x and y coordinate values represent the center of the pixel
* Date/time strings can be parsed using `datetime.fromisoformat`
* Only one coordinate system is used by all data variables (i.e. only one grid
  mapping variable is present in a file)

### Reference links

* https://wiki.esipfed.org/Attribute_Convention_for_Data_Discovery_1-3
* https://cfconventions.org/Data/cf-conventions/cf-conventions-1.11/cf-conventions.html

### NetCDF Attributes Used to Populate UMM-G

- **Required** required
- **RequiredC** conditionally required
- **R+** highly or strongly recommended
- **R** recommended
- **S** suggested

| Attribute in use (location)   | ACDD | CF Conventions | NSIDC Guidelines | Note    |
| ----------------------------- | ---- | -------------- | ---------------- | ------- |
| date_modified (global)        | S    |                | R                | 1       |
| time_coverage_start (global)  | R    |                | R                | 2       |
| time_coverage_end (global)    | R    |                | R                | 2       |
| crs_wkt (`crs` variable)      |      |                | R                | 3       |
| GeoTransform (`crs` variable) |      |                | R                | 4       |
| data (`x` variable)           |      |                | R                | 5       |
| data (`y` variable)           |      |                | R                | 6       |


| Attributes not currently used | ACDD | CF Conventions | NSIDC Guidelines | Comments |
| ----------------------------- | ---- | -------------- | ---------------- | -------- |
| Conventions (global)          | R+   | Required       | R                |          |
| standard_name (variable)      | R+   | R+             |                  |          |
| grid_mapping (data variable)  |      | RequiredC      | R+               | 7        |
| grid_mapping_name (variable)  |      | RequiredC      | R+               | 7        |
| `projection_x_coordinate` standard name (variable) |  | RequiredC  |     | 8        |
| `projection_y_coordinate` standard name (variable) |  | RequiredC  |     | 9        |
| axis (variable)               |      | R              |                  | 8, 9     |
| geospatial_bounds (global)    | R    |                | R                |          |
| geospatial_bounds_crs (global)| R    |                | R                |          |
| geospatial_lat_min (global)   | R    |                | R                |          |
| geospatial_lat_max (global)   | R    |                | R                |          |
| geospatial_lat_units (global) | R    |                | R                |          |
| geospatial_lon_min (global)   | R    |                | R                |          |
| geospatial_lon_max (global)   | R    |                | R                |          |
| geospatial_lon_units (global) | R    |                | R                |          |

Notes:
1. Used to populate the production date and time values in UMM-G output.
2. Used to populate the time begin and end UMM-G values.
3. The `crs_wkt` ("well known text") value is handed to the
   `CRS` and `Transformer` modules in `pyproj` to conveniently deal
   with the reprojection of (y,x) values to EPSG 4326 (lon, lat) values.
4. The `GeoTransform` value provides the pixel size per data value, which is then used
   to calculate the padding added to x and y values to create a GPolygon enclosing all
   of the data.
5. The `x` coordinate variable values are reprojected and thinned to create a GPolygon.
6. The `y` coordinate variable values are reprojected and thinned to create a GPolygon.
7. A grid mapping variable is required if the horizontal spatial coordinates are not
   longitude and latitude and the intent of the data provider is to geolocate
   the data. `grid_mapping` and `grid_mapping_name` allow programmatic identification of
   the variable holding information about the horizontal coordinate reference system.
   `metgenc` code currently assumes a variable named `crs` exists with grid
   information. **TODO:** Identify the coordinate reference system variable by
   looking for the `grid_mapping_name` or `grid_mapping` attribute.
8. `metgenc` code currently assumes a coordinate variable `x` exists whose
   data values represent spatial information in meters.
   **TODO:** Identify the x-axis coordinate variable by looking for the `standard_name`
   attribute with a value of `projection_x_coordinate`, or an `axis` attribute with
   the value `X`, rather than assuming the variable is named `x`.
9. `metgenc` code currently assumes a coordinate variable `y` exists whose
   data values represent spatial information in meters.
   **TODO:** Identify the y-axis coordinate variable by looking for the `standard_name`
   attribute with a value of `projection_y_coordinate`, or an `axis` attribute with
   the value `Y`, rather than assuming the variable is named `x`.


## Installing MetGenC

MetGenC can be installed from [PyPI](https://pypi.org/). First, create a
Python virtual environment in a directory of your choice, then activate
it:

    $ python -m venv /Users/afitzger/metgenc (i.e. provide the path to and name of the virtual environment to house MetgenC)
    $ source ~/metgenc/bin/activate (i.e., source your newly created virtual environment name)

Now install MetGenC into the virtual environment using `pip`:

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

Finally, restrict the permissions of the directory and files:

    $ chmod -R go-rwx ~/.aws

When you obtain the AWS key pair ([covered here](https://nsidc.atlassian.net/l/cp/4LNZPggJ)), edit the `~/.aws/credentials` file
and replace `TBD` with the public and secret key values.

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

If you require access to multiple AWS accounts, each with their own configuration--for
example, different accounts for pre-production vs. production--you can use the AWS CLI
'profile' feature to manage settings for each account. See the [AWS configuration
documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html#cli-configure-files-using-profiles)
for the details.

## Usage
When you have data files, a Cumulus Collection and its Rules established in the Cumulus Dashboard, you’re ready to run
MetGenC to generate umm-g files, cnm messages, and kick off data ingest directly to Cumulus! Note: MetGenC can be run without
a Cumulus Collection ready, it will only function to output umm-g metadata files and cnm messages.

### Familiarizing Yourself with MetGenC

* Show the help text:

        $ metgenc --help
```
  Usage: metgenc [OPTIONS] COMMAND [ARGS]...

  The metgenc utility allows users to create granule-level metadata, stage
  granule files and their associated metadata to Cumulus, and post CNM
  messages.

Options:
  --help  Show this message and exit.`

Commands:
  info     Summarizes the contents of a configuration file.
  init     Populates a configuration file based on user input.
  process  Processes science data files based on configuration file...
  validate Validates the contents of local JSON files.
```

  For detailed help on each command, run: metgenc <command> --help`, for example:

        $ metgenc process --help
  ```
  Usage: metgenc process [OPTIONS]

  Processes science data files based on configuration file contents.

Options:
  -c, --config TEXT   Path to configuration file  [required]
  -e, --env TEXT      environment  [default: uat]
  -n, --number count  Process at most 'count' granules.
  -wc, --write-cnm    Write CNM messages to files.
  -o, --overwrite     Overwrite existing UMM-G files.
  --help              Show this message and exit.
  ```

* Show summary information about a `metgenc` configuration file. Here we use the example configuration file provided in the repo:

        $ metgenc info --config example/modscg.ini

* Process science data and stage it for Cumulus:

        # Source the AWS profile (once) before running 'process'-- use 'default' or a named profile
        $ source metgenc-env.sh default
        $ metgenc process --config example/modscg.ini

* Validate JSON output

        $ metgenc validate -c example/modscg.ini -t cnm

  The package `check-jsonschema` is also installed by MetGenC and can be used to validate a single file:

        $ check-jsonschema --schemafile <path to schema file> <path to CNM file>

* Exit the Poetry shell:

        $ exit

## Troubleshooting

TBD

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

* Update the CHANGELOG to include details of the changes included in the new
  release. The version should be the string literal 'UNRELEASED' (without
  single-quotes). It will be replaced with the actual version number after
  we bump the version below. Commit the CHANGELOG so the working directory is
  clean.

* Show the current version and the possible next versions:

        $ bump-my-version show-bump
        0.3.0 ── bump ─┬─ major ─ 1.0.0
                       ├─ minor ─ 0.4.0
                       ╰─ patch ─ 0.3.1

* Bump the version to the desired number, for example:

        $ bump-my-version bump minor

  You will see the latest commit & tag by looking at `git log`. You can then
  push these to GitHub (`git push --follow-tags`) to trigger the CI/CD
  workflow.

* On the [GitHub repository](https://github.com/nsidc/granule-metgen), click
  'Releases' and follow the steps documented on the
  [GitHub Releases page](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository#creating-a-release).
  Draft a new Release using the version tag created above. After you have
  published the release, the MetGenC Publish GHA workflow will be started.
  Check that the workflow succeeds on the
  [MetGenC Actions page](https://github.com/nsidc/granule-metgen/actions),
  and verify that the
  [new MetGenC release is available on PyPI](https://pypi.org/project/nsidc-metgenc/).

## Credit

This content was developed by the National Snow and Ice Data Center with funding from
multiple sources.
