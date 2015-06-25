import re, click
from shub import auth

@click.command(help='add Scrapinghug API key into the netrc file')
@click.pass_context
def cli(context):
    if auth.get_key_netrc():
        context.fail('Key already exists in netrc file')
    key = raw_input('Insert your Scrapinghub API key: ')

    if key and is_valid_key(key):
        auth.write_key_netrc(key)
    else:
        context.fail('Invalid key')

def is_valid_key(key):
    return bool(re.match(r'[A-Fa-f\d]{32}$', key))
