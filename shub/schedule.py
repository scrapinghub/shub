from __future__ import absolute_import
import json

import click
from scrapinghub import ScrapinghubClient, ScrapinghubAPIError
from six.moves.urllib.parse import urljoin

from shub.exceptions import RemoteErrorException
from shub.config import get_target_conf


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
DEFAULT_PRIORITY = 2


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('spider', type=click.STRING)
@click.option('-a', '--argument',
              help='Spider argument (-a name=value)', multiple=True)
@click.option('-s', '--set',
              help='Job-specific setting (-s name=value)', multiple=True)
@click.option('-p', '--priority', type=int, default=DEFAULT_PRIORITY,
              help='Job priority (-p number). From 0 (lowest) to 4 (highest)')
@click.option('-e', '--environment', multiple=True,
              help='Job environment variable (-e VAR=VAL)')
@click.option('-u', '--units', type=int,
              help='Amount of Scrapy Cloud units (-u number)')
@click.option('-t', '--tag',
              help='Job tags (-t tag)', multiple=True)
def cli(spider, argument, set, environment, priority, units, tag):
    try:
        target, spider = spider.rsplit('/', 1)
    except ValueError:
        target = 'default'
    targetconf = get_target_conf(target)
    job_key = schedule_spider(targetconf.project_id, targetconf.endpoint,
                              targetconf.apikey, spider, argument, set,
                              priority, units, tag, environment)
    watch_url = urljoin(
        targetconf.endpoint,
        '../p/{}/{}/{}'.format(*job_key.split('/')),
    )
    short_key = job_key.split('/', 1)[1] if target == 'default' else job_key
    click.echo("Spider {} scheduled, job ID: {}".format(spider, job_key))
    click.echo("Watch the log on the command line:\n    shub log -f {}"
               "".format(short_key))
    click.echo("or print items as they are being scraped:\n    shub items -f "
               "{}".format(short_key))
    click.echo("or watch it running in Zyte's web interface:\n    {}"
               "".format(watch_url))


def schedule_spider(project, endpoint, apikey, spider, arguments=(), settings=(),
                    priority=DEFAULT_PRIORITY, units=None, tag=(), environment=()):
    client = ScrapinghubClient(apikey, dash_endpoint=endpoint)
    try:
        project = client.get_project(project)
        args = dict(x.split('=', 1) for x in arguments)
        cmd_args = args.pop('cmd_args', None)
        meta = args.pop('meta', None)
        job = project.jobs.run(
            spider=spider,
            meta=json.loads(meta) if meta else {},
            cmd_args=cmd_args,
            job_args=args,
            job_settings=dict(x.split('=', 1) for x in settings),
            priority=priority,
            units=units,
            add_tag=tag,
            environment=dict(x.split('=', 1) for x in environment),
        )
        return job.key
    except ScrapinghubAPIError as e:
        raise RemoteErrorException(str(e))
