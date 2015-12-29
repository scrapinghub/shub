from __future__ import absolute_import
import click
import requests
from six.moves import input
from six.moves.urllib.parse import urljoin

from shub.config import load_shub_config, update_config
from shub.exceptions import AlreadyLoggedInException


HELP = """
Add your Scrapinghub API key to your global configuration file
(~/.scrapinghub.yml). This is necessary to gain access to projects associated
with your Scrapinghub account.

You can find your API key in Scrapinghub's dashboard:
https://dash.scrapinghub.com/account/apikey
"""

SHORT_HELP = "Save your Scrapinghub API key"


@click.command(help=HELP, short_help=SHORT_HELP)
def cli():
    global_conf = load_shub_config(load_local=False, load_env=False)
    if 'default' in global_conf.apikeys:
        raise AlreadyLoggedInException

    conf = load_shub_config()
    key = _get_apikey(
        suggestion=conf.apikeys.get('default'),
        endpoint=global_conf.endpoints.get('default'),
    )
    with update_config() as conf:
        conf.setdefault('apikeys', {})
        conf['apikeys']['default'] = key


def _get_apikey(suggestion='', endpoint=None):
    suggestion_txt = ' (%s)' % suggestion if suggestion else ''
    click.echo(
        "Enter your API key from https://dash.scrapinghub.com/account/apikey"
    )
    key = ''
    while True:
        key = input('API key%s: ' % suggestion_txt) or suggestion
        click.echo("Validating API key...")
        if _is_valid_apikey(key, endpoint=endpoint):
            click.echo("API key is OK, you are logged in now.")
            return key
        else:
            click.echo("API key failed, try again.")


def _is_valid_apikey(key, endpoint=None):
    endpoint = endpoint or "https://dash.scrapinghub.com/api/scrapyd/"
    validate_api_key_endpoint = urljoin(endpoint, "../v2/users/me")
    r = requests.get("%s?apikey=%s" % (validate_api_key_endpoint, key))
    return r.status_code == 200
