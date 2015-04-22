import click
import sys


def log(message):
    click.echo(message)


def fail(message, code=1):
    log(message)
    sys.exit(code)
