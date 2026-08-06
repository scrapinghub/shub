from __future__ import absolute_import
import json
import click

from shub.utils import get_job


HELP = """
Given a job ID, fetch stats for that job from Scrapy Cloud and output them as
JSON.

A job ID consists of the Scrapinghub project ID, the numerical spider ID, and
the job ID, separated by forward slashes, e.g.:

    shub stats 12345/2/15

You can also provide the Scrapinghub job URL instead:

    shub stats https://app.scrapinghub.com/p/12345/2/15

You can omit the project ID if you have a default target defined in your
scrapinghub.yml:

    shub stats 2/15

Or use any target defined in your scrapinghub.yml:

    shub stats production/2/15

"""

SHORT_HELP = "Fetch stats from Scrapy Cloud"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('job_id')
def cli(job_id):
    job = get_job(job_id)
    click.echo(json.dumps(job.metadata.get('scrapystats', {})))
