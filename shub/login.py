import os
import re
import click
from shub.utils import get_key_netrc, NETRC_FILE

SH_TOP_LEVEL_DOMAIN = 'scrapinghub.com'


@click.command(help='add Scrapinghug API key into the netrc file')
@click.pass_context
def cli(context):
    if get_key_netrc():
        context.fail('Key already exists in netrc file')
    key = raw_input('Insert your Scrapinghub API key: ')
    if key and is_valid_key(key):
        descriptor = os.open(
            NETRC_FILE,
            os.O_CREAT | os.O_RDWR | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, 'a+') as out:
            line = 'machine {0} login {1} password ""\n'.format(
                SH_TOP_LEVEL_DOMAIN, key)
            out.write(line)
    else:
        context.fail('Invalid key')


def is_valid_key(key):
    return bool(re.match(r'[A-Fa-f\d]{32}$', key))
