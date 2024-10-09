<p align="center">
  <img alt="NSIDC logo" src="https://nsidc.org/themes/custom/nsidc/logo.svg" width="150" />
</p>

# nsidc-metgen

`nsidc-metgen` enables data producers as well as Operations staff managing the
data ingest workflow to create metadata files conforming to
NASA's Common Metadata Repository UMM-G specification."

## Level of Support

This repository is fully supported by NSIDC. If you discover any problems or bugs,
please submit an Issue. If you would like to contribute to this repository, you may fork
the repository and submit a pull request.

See the [LICENSE](LICENSE) for details on permissions and warranties. Please contact
nsidc@nsidc.org for more information.

## Requirements

To use the `nsidc-metgen` command-line tool, `instameta`, you must first have
Python version 3.12 installed. To determine the version of Python you have, run
this at the command-line:

    $ python --version

or

    $ python3 --version

Next, install [Poetry](https://python-poetry.org/) by using the [official
installer](https://python-poetry.org/docs/#installing-with-the-official-installer)
if you’re comfortable with the instructions, or by installing it using a package
manager (like Homebrew) if this is more familiar to you. When successfully
installed, you should be able to run:

    $ poetry --version
    Poetry (version 1.8.3)

## Assumptions

- Checksums are all SHA256

## Installation

Make a local directory (i.e., on your computer), and then `cd` into that
directory. Clone the `granule-metgen` repository using ssh if you have [added
ssh keys to your GitHub
account](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account)
or https if you have not:

    $ mkdir -p ~/my-projects; cd ~/my-projects
    # Install using ssh:
    $ git clone git@github.com:nsidc/granule-metgen.git
    # Install using https:
    $ git clone https://github.com/nsidc/granule-metgen.git

Enter the `granule-metgen` directory and run Poetry to have it install the `granule-metgen` dependencies. Then start a new shell in which you can run the tool:

    $ cd granule-metgen
    $ poetry install
    $ poetry shell

With the Poetry shell running, start the instameta tool and verify that it’s working by requesting its usage options and having them returned:

    $ instameta --help
    Usage: instameta [OPTIONS] COMMAND [ARGS]...

    Options:
      --help  Show this message and exit.

    Commands:
      info
      init
      process

## AWS Credentials

In order to process science data and stage it for Cumulus, you must first create & setup your AWS
credentials. Several options for doing this are given here:

### Manually Creating Configuration Files

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

### Using the AWS CLI

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

* Show the help text:

        $ instameta --help

* Show the help text for an individual command:

        $ instameta init --help

* Show summary information about an `instameta` configuration file. Here we use the example configuration file provided in the repo:

        $ instameta info --config example/modscg.ini

* Process science data and stage it for Cumulus:

        # Source the AWS profile (once) before running 'process'-- use 'default' or a named profile
        $ source scripts/env.sh default
        $ instameta process --config example/modscg.ini

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
