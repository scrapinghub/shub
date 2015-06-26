import re
import click
import os
from shub import auth
from shub.click_utils import log
from six.moves import input


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
    return input(prompt)


def _find_cfg_key():
    cfg_key = _read_scrapy_cfg_key()
    if cfg_key:
        return cfg_key

    envkey = os.getenv("SHUB_APIKEY")
    if envkey:
        return envkey

def _read_scrapy_cfg_key():
    try:
        from scrapy.utils.conf import get_config
        cfg = get_config()

        if cfg.has_section('deploy'):
            deploy = dict(cfg.items('deploy'))
            key = deploy.get('username')

            if key:
                return key
    except:
        return
