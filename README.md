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

Next, install [Poetry](https://python-poetry.org/) by using the [official installer](https://python-poetry.org/docs/#installing-with-the-official-installer) if you’re comfortable with the instructions, or by installing it using a package manager (like Homebrew) if this is more familiar to you. When successfully installed, you should be able to run:

    $ poetry --version
    Poetry (version 1.8.3)

## Installation

Make a local directory (i.e., on your computer), and then `cd` into that directory. Clone the `granule-metgen` repository using ssh if you have [added ssh keys to your GitHub account](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account) or https if you have not:

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
