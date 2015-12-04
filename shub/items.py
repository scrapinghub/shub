import click
from click import ClickException
from hubstorage import HubstorageClient
from shub.utils import find_api_key, is_valid_jobid


@click.command(help='Get items of a given job on Scrapy Cloud')
@click.pass_context
@click.argument('job_id')
def cli(context, job_id):
    if not is_valid_jobid(job_id):
        raise ClickException('Invalid job ID. Job ID must be: projectid/spiderid/jobid')
    apikey = find_api_key()
    if not apikey:
        raise ClickException('Scrapinghub API key not found: please, run \'scrapy login\' first')
    for item in fetch_items_for_job(apikey, job_id):
        click.echo(item)


def fetch_items_for_job(apikey, job_id):
    hc = HubstorageClient(auth=apikey)
    job = hc.get_job(job_id)
    if not job.metadata:
        raise ClickException('The job {} doesn\'t exist'.format(job_id))
    return job.items.iter_values()
