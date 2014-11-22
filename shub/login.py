import os, click, json
from shub.utils import get_key_netrc, NETRC_FILE

@click.command(help='create a configuration file for shub')
def cli():
    if get_key_netrc():
        print 'Key already exists in netrc file'
        return
    key = raw_input('Insert your Scrapy Cloud API key: ')
    if key:
        with open(NETRC_FILE, 'a+') as out:
            line = 'machine scrapinghub.com login {0} password ""'.format(key)
            out.write(line)
    else:
        print 'Invalid key'
