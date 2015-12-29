import click

from shub.utils import job_resource_iter, get_job


HELP = """
Given a job ID, fetch requests made for that job from Scrapy Cloud and output
them as JSON lines.

A job ID consists of the Scrapinghub project ID, the numerical spider ID, and
the job ID, separated by forward slashes, e.g.:

    shub requests 12345/2/15

You can omit the project ID if you have a default target defined in your
scrapinghub.yml:

    shub requests 2/15

Or use any target defined in your scrapinghub.yml:

    shub requests production/2/15

If the job is still running, you can watch the requests as they are being made
by providing the -f flag:

    shub requests -f 2/15
"""


SHORT_HELP = "Fetch requests from Scrapy Cloud"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('job_id')
@click.option('-f', '--follow', help='output new requests as they are made',
              is_flag=True)
def cli(job_id, follow):
    job = get_job(job_id)
    for item in job_resource_iter(job.requests.iter_json, follow=follow):
        click.echo(item)
