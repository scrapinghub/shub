import sys, click
from shub.utils import get_key_netrc, NETRC_FILE

@click.command(help='add Scrapinghug API key into the netrc file')
def cli():
    if get_key_netrc():
        sys.stderr.write('Key already exists in netrc file\n')
        sys.exit(1)
    key = raw_input('Insert your Scrapinghub API key: ')
    if key:
        with open(NETRC_FILE, 'a+') as out:
            line = 'machine scrapinghub.com login {0} password ""'.format(key)
            out.write(line)
    else:
        sys.stderr.write('Invalid key\n')
        sys.exit(1)
