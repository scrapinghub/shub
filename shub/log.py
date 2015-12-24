import logging
from datetime import datetime

from shub.utils import get_job

import click


@click.command(help='Get log of a given job on Scrapy Cloud')
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
