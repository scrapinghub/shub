import logging
from datetime import datetime

from shub.utils import get_job

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
"""

SHORT_HELP = "Fetch log from Scrapy Cloud"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('job_id')
def cli(job_id):
    job = get_job(job_id)
    for item in job.logs.iter_values():
        click.echo(
            "{} {} {}".format(
                datetime.utcfromtimestamp(item['time']/1000),
                logging.getLevelName(int(item['level'])),
                item['message']
            )
        )
