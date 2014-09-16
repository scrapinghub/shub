import os, click, json

@click.command(help='create a configuration file for shub')
def cli():
    home_cfg = os.path.expanduser('~/.shub.cfg')
    if os.path.isfile(home_cfg):
        overwrite = raw_input(
            'File [%s] already exists. Would you like to overwrite it? [yes/NO]: ' % home_cfg
        )
        if overwrite.lower() != 'yes':
            print 'Quiting...'
            return
    config = {
        'auth': {
            'key': raw_input('Insert your Scrapy Cloud API key: '),
        },
    }
    with open(home_cfg, 'w') as out:
        out.write(json.dumps(config, indent=4))
