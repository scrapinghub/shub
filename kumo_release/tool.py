import click
import importlib
import kumo_release
from kumo_release.utils import missing_modules


def missingmod_cmd(modules):
    modlist = ", ".join(modules)

    @click.command(help="*DISABLED* - requires %s" % modlist)
    @click.pass_context
    def cmd(ctx):
        click.echo("Error: '%s' command requires %s" %
                   (ctx.info_name, modlist))
        ctx.exit(1)
    return cmd


@click.group(help="Scrapinghub release tool")
@click.version_option(kumo_release.__version__)
def cli():
    pass


module_deps = {
    "init": [],
    "build": ["docker"],
    "test": ["docker"],
    "push": ["docker"],
    "deploy": ["scrapy"],
    "upload": ["scrapy", "docker"],
    "check": [],
}

for command, modules in module_deps.items():
    m = missing_modules(*modules)
    if m:
        cli.add_command(missingmod_cmd(m), command)
    else:
        module_path = "kumo_release." + command
        command_module = importlib.import_module(module_path)
        cli.add_command(command_module.cli, command)
