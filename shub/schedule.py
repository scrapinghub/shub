import json

import click

from click import ClickException
from scrapinghub import Connection, APIError
from six.moves.urllib.parse import urljoin

from shub.config import get_target


HELP = """
Schedule a spider to run on Scrapy Cloud, optionally with provided spider
arguments and job-specific settings.

The `spider` argument should match the spider's name, e.g.:

    shub schedule myspider

By default, shub will schedule the spider in your default project (as defined
in scrapinghub.yml). You may also explicitly specify the project to use by
supplying its ID:

    shub schedule 12345/myspider

Or by supplying an identifier defined in scrapinghub.yml:

    shub schedule production/myspider

Spider arguments can be supplied through the -a option:

    shub schedule myspider -a ARG1=VALUE1 -a ARG2=VALUE2

Similarly, job-specific settings can be supplied through the -s option:

    shub schedule myspider -s SETTING=VALUE -s LOG_LEVEL=DEBUG
"""

SHORT_HELP = "Schedule a spider to run on Scrapy Cloud"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('spider', type=click.STRING)
@click.option('-a', '--argument',
              help='spider argument (-a name=value)', multiple=True)
@click.option('-s', '--set',
              help='job-specific setting (-s name=value)', multiple=True)
def cli(spider, argument, set):
    try:
        target, spider = spider.rsplit('/', 1)
    except ValueError:
        target = 'default'
    project, endpoint, apikey = get_target(target)
    job_key = schedule_spider(project, endpoint, apikey, spider, argument, set)
    watch_url = urljoin(
        endpoint,
        '../../p/{}/job/{}/{}'.format(*job_key.split('/')),
    )
    click.echo(
        'Spider {} scheduled, watch it running here:\n{}'
        ''.format(spider, watch_url)
    )


def schedule_spider(project, endpoint, apikey, spider, arguments=(),
                    settings=()):
    conn = Connection(apikey, url=urljoin(endpoint, '..'))
    try:
        return conn[project].schedule(
            spider,
            job_settings=json.dumps(dict(x.split('=') for x in settings)),
            **dict(x.split('=') for x in arguments)
        )
    except APIError as e:
        raise ClickException(e.message)
