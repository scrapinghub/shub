import click
import os
import requests
from shub import auth
from six.moves import input
from shub.scrapycfg import get_config


@click.command(help='add Scrapinghug API key into the netrc file')
@click.pass_context
def cli(context):
    if auth.get_key_netrc():
        click.echo("You're already logged in. To change credentials, use 'shub logout' first.")
        return 0

    cfg_key = _find_cfg_key()
    key = _get_apikey(suggestion=cfg_key)
    auth.write_key_netrc(key)


def _get_apikey(suggestion=''):
    suggestion_txt = ' (%s)' % suggestion if suggestion else ''
    click.echo('Enter your API key from https://dash.scrapinghub.com/account/apikey')
    key = ''
    while True:
        key = input('API key%s: ' % suggestion_txt)
        click.echo("Validating API key...")
        if _is_valid_apikey(key):
            click.echo("API key is OK, you are logged in now.")
            return key
        else:
            click.echo("API key failed, try again.")


def _is_valid_apikey(key):
    validate_api_key_endpoint = "https://dash.scrapinghub.com/api/v2/users/me"
    r = requests.get("%s?apikey=%s" % (validate_api_key_endpoint, key))
    return r.status_code == 200


def _find_cfg_key():
    cfg_key = _read_scrapy_cfg_key()
    if cfg_key:
        return cfg_key

    envkey = os.getenv("SHUB_APIKEY")
    if envkey:
        return envkey


def _read_scrapy_cfg_key():
    try:
        cfg = get_config()

        if cfg.has_section('deploy'):
            deploy = dict(cfg.items('deploy'))
            key = deploy.get('username')

            if key:
                return key
    except:
        return
