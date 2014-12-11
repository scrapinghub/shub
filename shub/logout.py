import re, click
from shub.utils import get_key_netrc, NETRC_FILE

@click.command(help='remove Scrapinghug API key from the netrc file')
@click.pass_context
def cli(context):
    if not get_key_netrc():
        context.fail('Key not found in netrc file')
    with open(NETRC_FILE, 'r+') as out:
        key_re = r'machine\s+scrapinghub\.com\s+login\s+\w+\s+password\s+""\s*'
        content = out.read()
        content_new = re.sub(key_re, '', content)
        if content_new != content:
            out.seek(0)
            out.truncate()
            out.write(content_new)
    if get_key_netrc():
        context.fail(
            'Error removing key from the netrc file.'
            'Please, open the file ~/.netrc and remove it manually')
