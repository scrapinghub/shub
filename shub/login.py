import re, click
from shub.utils import get_key_netrc, NETRC_FILE

@click.command(help='add Scrapinghug API key into the netrc file')
@click.pass_context
def cli(context):
    if get_key_netrc():
        context.fail('Key already exists in netrc file')
    key = raw_input('Insert your Scrapinghub API key: ')
    if key and is_valid_key(key):
        with open(NETRC_FILE, 'a+') as out:
            line = 'machine scrapinghub.com login {0} password ""'.format(key)
            out.write(line)
    else:
        context.fail('Invalid key')

def is_valid_key(key):
    return bool(re.match(r'[A-Fa-f\d]{32}$', key))
