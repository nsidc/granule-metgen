<p align="center">
  <img alt="NSIDC logo" src="https://nsidc.org/themes/custom/nsidc/logo.svg" width="150" />
</p>

# MetGenC

![push workflow](https://github.com/nsidc/granule-metgen/actions/workflows/push.yml/badge.svg)
![workflow workflow](https://github.com/nsidc/granule-metgen/actions/workflows/workflow.yml/badge.svg)

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

Next, install the AWS commandline interface (CLI) by [following the appropriate
instructions for your platform](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).

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
- Date/time strings can be parsed using `datetime.fromisoformat`

## Installation

MetGenC can be installed from [PyPI](https://pypi.org/)

    $ pip install nsidc-metgenc

That's it! Now we're ready to run MetGenC and see what it can do:

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

* Show summary information about an `metgenc` configuration file. Here we use the example configuration file provided in the repo:

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

### Run tests

        $ poetry run pytest

### Run tests when source changes (uses [pytest-watcher](https://github.com/olzhasar/pytest-watcher)):

        $ poetry run ptw . --now --clear

### Releasing

* Update the CHANGELOG to reflect the latest version and the
  changes included in the release.

* Show the current version and the possible next versions:

        $ bump-my-version show-bump
        0.3.0 ── bump ─┬─ major ─ 1.0.0
                       ├─ minor ─ 0.4.0
                       ╰─ patch ─ 0.3.1

* Bump the version to the desired number:

        $ bump-my-version bump minor

  You will see the latest commit & tag by looking at `git log`. You
  can then push these to GitHub to trigger the CI/CD workflow.

## Credit

This content was developed by the National Snow and Ice Data Center with funding from
multiple sources.
