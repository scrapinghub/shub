from __future__ import absolute_import
import click

from scrapinghub import ScrapinghubClient
from shub.config import load_shub_config

HELP = """
Delete or cancel jobs from Scrapy Cloud's project.

A project ID must be passed as argument:

    shub delete 12345

You can select jobs from a specific Spider:

    shub delete 12345 --spider-id=67

Or a specific state ("pending" or "finished" only):

    shub delete 12345 --state=pending

Or both:

    shub delete 12345 --spider-id=67 --state=finished

You can also run it in "force" mode, so it won't ask you permission before flushing jobs.
    shub delete 12345 --force
"""

SHORT_HELP = "Delete or cancel jobs from Scrapy Cloud"

EXPECTED_STATES = ('pending', 'finished')


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('project_id')
@click.option('--spider-id', required=False)
@click.option('--state', required=False)
@click.option('--force', '-f', is_flag=True)
def cli(project_id, spider_id, state, force):
    if state is None:
        state = EXPECTED_STATES
    elif state not in EXPECTED_STATES:
        print('unexpected state, must be: {}'.format(
            'or '.join(EXPECTED_STATES)
        ))
        exit(10)

    client = _get_client()
    project = client.get_project(project_id)

    if spider_id is not None:
        spider = _get_spider(spider_id, project)
        spider_name = spider.name
    else:
        spider_name = None

    filters = {
        "spider": spider_name,
        "state": state
    }

    counter = project.jobs.count(**filters)
    if counter == 0:
        print('no jobs to remove.')
        exit(0)

    if force is not True:
        yesno = input('{} jobs to remove, are your sure? [Y/n]\n'.format(
            counter
        )).lower().strip()

        if yesno not in ('', 'y'):
            print('aborted.')
            exit(1)

    for job in project.jobs.iter(**filters):
        job = project.jobs.get(job['key'])
        state = job.metadata.get('state')

        if state == 'pending':
            action = 'cancel'
        else:
            action = 'delete'

        getattr(job, action)()
        print('job {} ({}) is deleted'.format(
            job.key,
            state,
            action
        ))


def _get_spider(spider_id, project):
    for spider in project.spiders.iter():
        spider = project.spiders.get(spider['id'])
        if int(spider.key.split('/')[1]) == int(spider_id):
            return spider


def _get_client():
    conf = load_shub_config()
    endpoint = conf.get_endpoint(0)
    apikey = conf.get_apikey(0)

    client = ScrapinghubClient(apikey, dash_endpoint=endpoint)
    return client
