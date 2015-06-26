import re
import click
import os
from shub import auth
from scrapy.utils.conf import get_config
from shub.click_utils import log


@click.command(help='add Scrapinghug API key into the netrc file')
@click.pass_context
def cli(context):
    if auth.get_key_netrc():
        context.fail('Already logged in. To logout use: shub logout')

    cfg_key = _find_cfg_key()
    key = _prompt_for_key(suggestion=cfg_key)

    if not key and is_valid_key(cfg_key):
        auth.write_key_netrc(cfg_key)
    elif key and is_valid_key(key):
        auth.write_key_netrc(key)
    else:
        context.fail('Invalid key. Tip: your key must have 32 characters.')
    log('Success.')


def is_valid_key(key):
    return bool(re.match(r'[A-Fa-f\d]{32}$', key))


def _prompt_for_key(suggestion):
    suggestion_txt = ''
    if suggestion:
        suggestion_txt = '(%s) ' % suggestion

    prompt = 'Insert your Scrapinghub API key %s: ' % suggestion_txt
    return raw_input(prompt)


def _find_cfg_key():
    try:
        cfg = get_config()
    except:
        return

    if cfg.has_section('deploy'):
        deploy = dict(cfg.items('deploy'))
        key = deploy.get('username')

        if key:
            return key

    envkey = os.getenv("SHUB_APIKEY")
    if envkey:
        return envkey
