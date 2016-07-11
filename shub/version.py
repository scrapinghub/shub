from __future__ import absolute_import
import click
import shub


@click.command(help="Show shub version")
def cli():
    click.echo(shub.__version__)
