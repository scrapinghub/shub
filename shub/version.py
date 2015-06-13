import click
import shub


@click.command(help="Show shub version")
def cli():
    print(shub.__version__)
