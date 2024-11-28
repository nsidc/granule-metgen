<p align="center">
  <img alt="NSIDC logo" src="https://nsidc.org/themes/custom/nsidc/logo.svg" width="150" />
</p>

# MetGenC

The `MetGenC` toolkit enables Operations staff and data
producers to create metadata files conforming to NASA's Common Metadata Repository UMM-G
specification and ingest data directly to NASA EOSDIS’s Cumulus archive. Cumulus is an
open source cloud-based data ingest, archive, distribution, and management framework
developed for NASA's Earth Science data.

## Level of Support

This repository is fully supported by NSIDC. If you discover any problems or bugs,
please submit an Issue. If you would like to contribute to this repository, you may fork
the repository and submit a pull request.

See the [LICENSE](LICENSE) for details on permissions and warranties. Please contact
nsidc@nsidc.org for more information.

## Requirements

To use the `nsidc-metgen` command-line tool, `metgenc`, you must first have
Python version 3.12 installed. To determine the version of Python you have, run
this at the command-line:

    $ python --version

or

    $ python3 --version

Next, you must also install [Poetry](https://python-poetry.org/) either by using the [official
installer](https://python-poetry.org/docs/#installing-with-the-official-installer)
if you’re comfortable following the instructions, or by using a package
manager (like Homebrew) if this is more familiar to you. When successfully
installed, you should be able to run:

    $ poetry --version
    Poetry (version 1.8.3)

Lastly, you will need to create & setup AWS credentials for yourself. The ways in which
this can be accomplished are detailed in the **AWS Credentials** section below.

## Assumptions

- Checksums are all SHA256
- In the data files to be ingested:
  - The global attribute "date_modified" exists and will be used to represent
  the production date and time.
  - Global attributes "time_coverage_start" and "time_coverage_end" exist and
  will be used for the time range metadata values.
  - Only one coordinate system is used by all variables (i.e. only one grid mapping variable is present in a file)
  - (x[0],y[0]) represents the upper left corner of the spatial coverage.
  - x,y coordinates represent the center of the pixel
  - The grid mapping variable contains a GeoTransform attribute (which defines the pixel size ), and
  can be used to determine the padding added to x and y values.
- Only one coordinate system is used by all variables (i.e. only one grid_mapping)
- (x[0],y[0]) represents the upper left corner of the spatial coverage.
- x,y coordinates represent the center of the pixel.
- Date/time strings can be parsed using `datetime.fromisoformat`

https://wiki.esipfed.org/Attribute_Convention_for_Data_Discovery_1-3
https://cfconventions.org/Data/cf-conventions/cf-conventions-1.11/cf-conventions.html

**Required** required
**R+** highly or strongly recommended
**R** recommended
**S** suggested

| Attribute (location)         | ACDD | CF Conventions | NSIDC Guidelines | Comments |
| ---------------------------- | ---- | -------------- | ---------------- | -------- |
| date_modified (global)       | S    |                | R                | 6        |
| time_coverage_start (global) | R    |                | R                | 7
| time_coverage_end (global)   | R    |                | R                | 7
| standard_name (variable)     | R+   | R+             |                  |
| grid_mapping (data variable) |      | Required       |                  | 2 |
| grid_mapping_name (variable) |      | Required       | R+               | 2 
| crs_wkt (variable)           |      |                | R                | 5
| GeoTransform (variable)      |      |                | R                | 1 |
| var with standard_name of projection_x_coordinate  | | | R | 3
| var with standard_name of projection_y_coordinate  | | | R | 4 
| Conventions (global)         | R+   | Required | R | Not currently used by metgenc |

Notes
1. Associated with variable having grid_mapping_name attribute. Used to determine pixel size and padding added to x and y values.
2. Required for declaring horizontal coordinate reference system
3. currently assuming variable name x
4. currently assuming variable name y
5. Associated with grid_mapping_name variable
6. used to represent the production date and time.
7. Global attributes "time_coverage_start" and "time_coverage_end" exist and
  will be used for the time range metadata values.

use data from x and y coordinate variables

TODO:
x.data (need to change current assumption of x variable to look for variable with standard_name projection_x_coordinate or axis attribute)
y.data (need to change current assumption of y variable to look for variable with standard_name projection_y_coordinate)


R+ highly or strongly recommended
R recommended
S suggested
Required required


CF conventions
file has extension `.nc`
include discussion of units? time coordinate must have units
axis attribute identifies X and Y

NetCDF Users Guide
Groups and scoping in netCDF files -- not considered in our current handling


## Installation of MetGenC from GitHub

Make a local directory (i.e., on your computer), and then `cd` into that
directory. Clone the `granule-metgen` repository using ssh if you have [added
ssh keys to your GitHub
account](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account)
or via https if you haven't:

    $ mkdir -p ~/my-projects; cd ~/my-projects
    # Install using ssh:
    $ git clone git@github.com:nsidc/granule-metgen.git
  OR  
    # Install using https:
    $ git clone https://github.com/nsidc/granule-metgen.git

Enter the `granule-metgen` directory and run Poetry to have it install the `granule-metgen` dependencies. Then start a new shell in which you can run the tool:

    $ cd granule-metgen
    $ poetry install
    $ poetry shell

With the Poetry shell running, start the metgenc tool JUST to verify that it’s working by requesting its usage options and having them
returned. There’s more to do (detailed in the **Usage** section below) before MetGenC can be run to successfully create ummg files, cnm messages, and stage data to an S3 bucket for ingest!)::

    $ metgenc --help
    Usage: metgenc [OPTIONS] COMMAND [ARGS]...

    Options:
      --help  Show this message and exit.

    Commands:
      info
      init
      process

## AWS Credentials

In order to process science data and stage it for Cumulus, you must first create & setup your AWS
credentials. Two options for doing this are detailed here:

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

When you obtain the AWS key pair (not covered here), edit the `~/.aws/credentials` file
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
        $ source scripts/env.sh default
        $ metgenc process --config example/modscg.ini

* Validate JSON output

        $ metgenc validate -c example/modscg.ini -t cnm

  The package `check-jsonschema` is also installed by MetGenC and can be used to validate a single file:

        $ check-jsonschema --schemafile <path to schema file> <path to CNM file>

* Exit the Poetry shell:

        $ exit

## Troubleshooting

TBD

## Contributing

### Requirements

* [Python](https://www.python.org/) v3.12+
* [Poetry](https://python-poetry.org/docs/#installing-with-the-official-installer)

### Installing Dependencies

* Use Poetry to create and activate a virtual environment

        $ poetry shell

* Install dependencies

        $ poetry install

### Run tests:

        $ poetry run pytest

### Run tests when source changes (uses [pytest-watcher](https://github.com/olzhasar/pytest-watcher)):

        $ poetry run ptw . --now --clear

## Credit

This content was developed by the National Snow and Ice Data Center with funding from
multiple sources.
