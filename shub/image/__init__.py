import click
import importlib


@click.group(help="Release project with Docker")
def image_cli():
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
    module_path = "shub.image." + command
    command_module = importlib.import_module(module_path)
    image_cli.add_command(command_module.cli, command)
