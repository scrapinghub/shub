import click
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

# deploy
m = missing_modules('scrapy', 'setuptools')
if m:
    cli.add_command(missingmod_cmd(m), 'deploy')
else:
    from shub import deploy
    cli.add_command(deploy.cli, 'deploy')

# log
m = missing_modules('scrapinghub')
if m:
    cli.add_command(missingmod_cmd(m), 'log')
else:
    from shub import log
    cli.add_command(log.cli, 'log')
