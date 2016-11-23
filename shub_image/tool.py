import click
import importlib
import shub_image


@click.group(help="Scrapinghub release tool")
@click.version_option(shub_image.__version__)
def cli():
    pass


module_deps = [
    "init",
    "build",
    "list",
    "test",
    "push",
    "deploy",
    "upload",
    "check",
]

for command in module_deps:
    module_path = "shub_image." + command
    command_module = importlib.import_module(module_path)
    cli.add_command(command_module.cli, command)
