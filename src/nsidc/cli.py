import click


@click.command()
@click.option('--config', help='Instagram configuration file')
def cli():
    pass


if __name__ == "__main__":
    cli()
