from six.moves.urllib.parse import urljoin

import click

from click import ClickException
from scrapinghub import Connection, APIError

from shub.config import get_target


@click.command(help='Schedule a spider to run on Scrapy Cloud')
@click.argument('spider', type=click.STRING)
@click.option('-a', '--argument', help='argument for the spider (-a name=value)', multiple=True)
def cli(spider, argument):
    try:
        target, spider = spider.rsplit('/', 1)
    except ValueError:
        target = 'default'
    project, endpoint, apikey = get_target(target)
    job_key = schedule_spider(project, endpoint, apikey, spider, argument)
    watch_url = urljoin(
        endpoint,
        '../../p/{}/job/{}/{}'.format(*job_key.split('/')),
    )
    click.echo(
        'Spider {} scheduled, watch it running here:\n{}'
        ''.format(spider, watch_url)
    )


def schedule_spider(project, endpoint, apikey, spider, arguments=()):
    conn = Connection(apikey, url=urljoin(endpoint, '..'))
    try:
        return conn[project].schedule(spider, **dict(x.split('=') for x in arguments))
    except APIError as e:
        raise ClickException(e.message)
