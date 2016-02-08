import importlib

import click

import shub
from shub.utils import update_available


HELP = """
shub is the Scrapinghub command-line client. It allows you to deploy projects
or dependencies, schedule spiders, and retrieve scraped data or logs without
leaving the command line.
"""

SHORT_HELP = "Scrapinghub command-line client"

EPILOG = """
For usage and help on a specific command, run it with a --help flag, e.g.:

    shub schedule --help
"""


@click.group(help=HELP, short_help=SHORT_HELP, epilog=EPILOG)
@click.version_option(shub.__version__)
def cli():
    update_url = update_available()
    if update_url:
        click.echo("INFO: A newer version of shub is available. Update "
                   "via pip or get it at {}".format(update_url),  err=True)

commands = [
    "deploy",
    "login",
    "deploy_egg",
    "fetch_eggs",
    "deploy_reqs",
    "logout",
    "version",
    "items",
    "schedule",
    "log",
    "requests",
    "sync_project"
]

for command in commands:
    module_path = "shub." + command
    command_module = importlib.import_module(module_path)
    command_name = command.replace('_', '-')  # easier to type
    cli.add_command(command_module.cli, command_name)
