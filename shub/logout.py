import re, sys, click
from shub.utils import get_key_netrc, NETRC_FILE

@click.command(help='remove Scrapinghug API key from the netrc file')
def cli():
    if not get_key_netrc():
        sys.stderr.write('Key not found in netrc file\n')
        sys.exit(1)
    with open(NETRC_FILE, 'r+') as out:
        key_re = r'machine\s+scrapinghub\.com\s+login\s+\w+\s+password\s+""\s*'
        content = out.read()
        content = re.sub(key_re, '', content)
        out.seek(0)
        out.truncate()
        out.write(content)
    if get_key_netrc():
        sys.stderr.write(
            'Error removing key from the netrc file.'
            'Please, open the file ~/.netrc and remove it manually\n')
        sys.exit(1)
