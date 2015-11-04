import click
import os
import sys
import requests
from shub import auth
from shub.click_utils import log
from six.moves import input

VALIDATE_API_KEY_ENDPOINT = "https://dash.scrapinghub.com/api/v2/users/me"

@click.command(help='add Scrapinghug API key into the netrc file')
@click.pass_context
def cli(context):
    if auth.get_key_netrc():
        log("You're already logged in. To change credentials, use 'shub logout' first.")
        return 0

    cfg_key = _find_cfg_key()
    key = _ask_apikey(suggestion=cfg_key)
    auth.write_key_netrc(key)
    log('You are logged in now.')


def _ask_apikey(suggestion=''):
    suggestion_txt = ' (%s)' % suggestion if suggestion else ''
    print 'Enter your Scrapinghub API key from https://dash.scrapinghub.com/account/apikey'
    key = ''
    while True:
        key = input('API key%s: ' % suggestion_txt)
        print "Validating API key...",
        sys.stdout.flush()
        r = requests.get("%s?apikey=%s" % (VALIDATE_API_KEY_ENDPOINT, key))
        if r.status_code == 200:
            print "OK"
            return key
        else:
            print "Failed!"


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
