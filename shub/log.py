import logging
from datetime import datetime

from shub.utils import job_resource_iter, get_job

import click


HELP = """
Given a job ID, fetch the log of that job from Scrapy Cloud and print it.

A job ID consists of the Scrapinghub project ID, the numerical spider ID, and
the job ID, separated by forward slashes, e.g.:

    shub log 12345/2/15

You can omit the project ID if you have a default target defined in your
scrapinghub.yml:

    shub log 2/15

Or use any target defined in your scrapinghub.yml:

    shub log production/2/15

If the job is still running, you can watch the log as it is being written by
providing the -f flag:

    shub log -f 2/15
"""

SHORT_HELP = "Fetch log from Scrapy Cloud"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('job_id')
@click.option('-f', '--follow', help='output new log entries as they are '
              'produced', is_flag=True)
def cli(job_id, follow):
    job = get_job(job_id)
    for item in job_resource_iter(job.logs.iter_values, follow=follow,
                                  key_func=lambda item: item['_key']):
        click.echo(
            "{} {} {}".format(
                datetime.utcfromtimestamp(item['time']/1000),
                logging.getLevelName(int(item['level'])),
                item['message']
            )
        )
