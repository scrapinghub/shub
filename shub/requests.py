from __future__ import absolute_import
import click

from shub.utils import job_resource_iter, get_job


HELP = """
Given a job ID, fetch requests made for that job from Scrapy Cloud and output
them as JSON lines.

A job ID consists of the Scrapinghub project ID, the numerical spider ID, and
the job ID, separated by forward slashes, e.g.:

    shub requests 12345/2/15

You can also provide the Scrapinghub job URL instead:

    shub requests https://app.scrapinghub.com/p/12345/2/15

You can omit the project ID if you have a default target defined in your
scrapinghub.yml:

    shub requests 2/15

Or use any target defined in your scrapinghub.yml:

    shub requests production/2/15

If the job is still running, you can watch the requests as they are being made
by providing the -f flag:

    shub requests -f 2/15

Additional filters may be applied to the query:

    shub requests 12345/2/15 --filter '["url","icontains",["foo"]]'
"""

SHORT_HELP = "Fetch requests from Scrapy Cloud"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('job_id')
@click.option('-f', '--follow', help='output new requests as they are made',
              is_flag=True)
@click.option('-n', '--tail', help='output last N requests only', type=int)
@click.option('--filter', 'filter_', help='filter to be applied to the query')
def cli(job_id, follow, tail, filter_):
    job = get_job(job_id)
    for item in job_resource_iter(job, job.requests, output_json=True,
                                  follow=follow, tail=tail, filter_=filter_):
        click.echo(item)
