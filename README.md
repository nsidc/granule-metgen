<p align="center">
  <img alt="NSIDC logo" src="https://nsidc.org/themes/custom/nsidc/logo.svg" width="150" />
</p>

# granule-metgen

`granule-metgen` enables data producers as well as Operations staff managing the data ingest workflow to create metadata
files conforming to NSIDC's UMM-G guidelines.

## Level of Support

This repository is fully supported by NSIDC. If you discover any problems or bugs,
please submit an Issue. If you would like to contribute to this repository, you may fork
the repository and submit a pull request.

See the [LICENSE](LICENSE) for details on permissions and warranties. Please contact
nsidc@nsidc.org for more information.

## Requirements

To use the `granule-metgen` command-line tool, `instameta`, you must first have Python version 3.12 installed. To determine the version of Python you have, run this at the command-line:

    $ python --version

or

    $ python3 --version

Next, install [Poetry](https://python-poetry.org/) by using the [official installer](https://python-poetry.org/docs/#installing-with-the-official-installer). When successfully installed, you should be able to run:

    $ poetry --version

## Installation

Clone the `granule-metgen` repository into a local directory:

    $ mkdir -p ~/my-projects; cd ~/my-projects
    $ git clone git@github.com:nsidc/granule-metgen.git
    $ cd granule-metgen

Run Poetry and have it install the `granule-metgen` dependencies. Then start a new shell in which you can run the tool:

    $ poetry install
    $ poetry shell

Finally, run the `instameta` command-line tool and verify that it is available:

    $ instameta --help

## Usage

* Show the help text:

        $ instameta --help

* Show summary information about an `instameta` configuration file. Here we use the example configuration file provided in the repo:

        $ instameta info --config example/modscg.ini

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

### Running tests:

        $ poetry run pytest

## Credit

This content was developed by the National Snow and Ice Data Center with funding from
multiple sources.
