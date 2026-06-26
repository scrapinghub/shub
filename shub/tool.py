import importlib
import os

import click
from dotenv import dotenv_values, find_dotenv

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

CONTEXT_SETTINGS = {'help_option_names': ['-h', '--help']}


def _load_dotenv_apikey(dotenv_path: str | None) -> None:
    """Load SHUB_APIKEY from a .env file into the environment.

    Only the SHUB_APIKEY variable is read from the file; any other variables are ignored.
    A SHUB_APIKEY already present in the environment takes precedence over the value in
    the file. When ``dotenv_path`` is None, the nearest ``.env`` file in the current
    directory or its parents is used.
    """
    if 'SHUB_APIKEY' in os.environ:
        return
    apikey = dotenv_values(dotenv_path or find_dotenv(usecwd=True)).get('SHUB_APIKEY')
    if apikey:
        os.environ['SHUB_APIKEY'] = apikey


@click.group(help=HELP, short_help=SHORT_HELP, epilog=EPILOG,
             context_settings=CONTEXT_SETTINGS)
@click.option('--dotenv-path', default=None, type=click.Path(dir_okay=False),
              help="Path to a .env file to read the SHUB_APIKEY environment variable from."
                   " Defaults to the '.env' file in the current directory.")
@click.version_option(shub.__version__)
def cli(dotenv_path: str | None) -> None:
    _load_dotenv_apikey(dotenv_path)
    update_url = update_available()
    if update_url:
        click.echo("INFO: A newer version of shub is available. Update "
                   "via pip or get it at {}".format(update_url),  err=True)


commands = [
    "bootstrap",
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
    "copy_eggs",
    "migrate_eggs",
    "image",
    "cancel",
]

for command in commands:
    module_path = "shub." + command
    command_module = importlib.import_module(module_path)
    command_name = command.replace('_', '-')  # easier to type
    cli.add_command(command_module.cli, command_name)
