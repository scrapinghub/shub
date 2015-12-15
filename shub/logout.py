import click

from shub.config import load_shub_config, update_config


@click.command(help='Remove Scrapinghug API key from your .scrapinghub.yml')
def cli():
    global_conf = load_shub_config(load_local=False, load_env=False)
    if 'default' not in global_conf.apikeys:
        click.echo("You are not logged in.")
        return 0

    with update_config() as conf:
        del conf['apikeys']['default']
