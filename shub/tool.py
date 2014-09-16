import click, importlib
from shub.utils import missing_modules

def missingmod_cmd(modules):
    modlist = ", ".join(modules)
    @click.command(help="*DISABLED* - requires %s" % modlist)
    @click.pass_context
    def cmd(ctx):
        click.echo("Error: '%s' command requires %s" % (ctx.info_name, modlist))
        ctx.exit(1)
    return cmd

@click.group(help="Scrapinghub command-line client")
def cli():
    pass

module_deps = {
    "deploy": ["scrapy", "setuptools"],
    "log": ["requests"],
    "login": [],
}

for command, modules in module_deps.iteritems():
    m = missing_modules(*modules)
    if m:
        cli.add_command(missingmod_cmd(m), command)
    else:
        module_path = "shub." + command
        command_class = importlib.import_module(module_path)
        cli.add_command(command_class.cli, command)
