import click

from shub.config import load_shub_config, GLOBAL_SCRAPINGHUB_YML_PATH
from shub.utils import update_yaml_dict


HELP = """
Remove the Scrapinghub API key that is saved in your global configuration
file (~/.scrapinghub.yml), if any.
"""

SHORT_HELP = "Forget saved Scrapinghub API key"


@click.command(help=HELP, short_help=SHORT_HELP)
def cli():
    global_conf = load_shub_config(load_local=False, load_env=False)
    if 'default' not in global_conf.apikeys:
        click.echo("You are not logged in.")
        return 0

    with update_yaml_dict(GLOBAL_SCRAPINGHUB_YML_PATH) as conf:
        del conf['apikeys']['default']
