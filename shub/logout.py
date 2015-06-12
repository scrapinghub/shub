import re, click
from shub.utils import get_key_netrc, NETRC_FILE

@click.command(help='remove Scrapinghug API key from the netrc file')
@click.pass_context
def cli(context):
    if not get_key_netrc():
        context.fail('Key not found in netrc file')
    error_msg = remove_sh_key(NETRC_FILE)
    if error_msg:
        context.fail(error_msg)
    if get_key_netrc():
        context.fail(
            'Error removing key from the netrc file.'
            'Please, open the file ~/.netrc and remove it manually')

def remove_sh_key(netrc_file):
    error_msg = ''
    key_re = r'machine\s+scrapinghub\.com\s+login\s+\w+\s+password\s+""\s*'
    with open(netrc_file, 'r+') as out:
        content = out.read()
        content_new = re.sub(key_re, '', content)
        if content_new == content:
            error_msg = 'Regex didn\'t match. \
                         Key wasn\'t removed from netrc file'
        else:
            out.seek(0)
            out.truncate()
            out.write(content_new)
    return error_msg
