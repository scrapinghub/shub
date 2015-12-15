import click, importlib
import shub

@click.group(help="Scrapinghub command-line client")
@click.version_option(shub.__version__)
def cli():
    pass

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
]

for command in commands:
    module_path = "shub." + command
    command_module = importlib.import_module(module_path)
    command_name = command.replace('_', '-') # easier to type
    cli.add_command(command_module.cli, command_name)
