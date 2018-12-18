import click
import importlib


@click.group(help="Manage project based on custom Docker image")
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
    "run",
]

for command in module_deps:
    module_path = "shub.image." + command
    command_module = importlib.import_module(module_path)
    cli.add_command(command_module.cli, command)
