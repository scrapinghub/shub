import re, click
from shub.utils import fatal, get_key_netrc, NETRC_FILE

@click.command(help='add Scrapinghug API key into the netrc file')
def cli():
    if get_key_netrc():
        fatal('Key already exists in netrc file')
    key = raw_input('Insert your Scrapinghub API key: ')
    if key and is_valid_key(key):
        with open(NETRC_FILE, 'a+') as out:
            line = 'machine scrapinghub.com login {0} password ""'.format(key)
            out.write(line)
    else:
        fatal('Invalid key')

def is_valid_key(key):
    return bool(re.findall(r'^[A-Fa-f\d]{32}$', key))
