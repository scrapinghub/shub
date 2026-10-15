import click
import requests
from urllib.parse import urljoin

from shub.config import (load_shub_config, GLOBAL_SCRAPINGHUB_YML_PATH,
                         ShubConfig, _get_apikey_name)
from shub.exceptions import AlreadyLoggedInException
from shub.utils import update_yaml_dict


HELP = """
Add your Scrapinghub API key to your global configuration file
(~/.scrapinghub.yml). This is necessary to gain access to projects associated
with your Scrapinghub account.

You can find your API key in Scrapinghub's dashboard:
https://app.zyte.com/account/apikey
"""

SHORT_HELP = "Save your Scrapinghub API key"


@click.command(help=HELP, short_help=SHORT_HELP)
def cli():
    global_conf = load_shub_config(load_local=False, load_env=False)
    conf = load_shub_config()
    endpoint = conf.endpoints['default']
    apikey_name = _get_apikey_name(global_conf, endpoint)
    if apikey_name in global_conf.apikeys:
        raise AlreadyLoggedInException

    key = _get_apikey(
        suggestion=conf.apikeys.get('default'),
        endpoint=endpoint,
    )
    with update_yaml_dict(GLOBAL_SCRAPINGHUB_YML_PATH) as conf:
        conf.setdefault('apikeys', {})
        conf['apikeys'][apikey_name] = key


def _get_apikey(suggestion='', endpoint=None):
    suggestion_txt = ' (%s)' % suggestion if suggestion else ''
    click.echo(
        "Enter your API key from https://app.zyte.com/o/settings/apikey"
    )
    while True:
        key = input('API key%s: ' % suggestion_txt) or suggestion
        click.echo("Validating API key...")
        if _is_valid_apikey(key, endpoint=endpoint):
            click.echo("API key is OK, you are logged in now.")
            return key
        else:
            click.echo("API key failed, try again.")


def _is_valid_apikey(key, endpoint=None):
    endpoint = endpoint or ShubConfig.DEFAULT_ENDPOINT
    validate_api_key_endpoint = urljoin(endpoint, "v2/users/me")
    r = requests.get(validate_api_key_endpoint, params={'apikey': key})
    return r.status_code == 200
