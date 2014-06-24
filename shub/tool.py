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

m = missing_modules('scrapy', 'setuptools')
if m:
    cli.add_command(missingmod_cmd(m), 'deploy')
    cli.add_command(missingmod_cmd(m), 'status')
else:
    from shub import deploy
    from shub import status

    cli.add_command(deploy.cli, 'deploy')
    cli.add_command(status.cli, 'status')
