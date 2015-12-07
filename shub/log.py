import click
from click import ClickException
from hubstorage import HubstorageClient
from shub.utils import find_api_key, validate_jobid


@click.command(help='Get log of a given job on Scrapy Cloud')
@click.pass_context
@click.argument('job_id')
def cli(context, job_id):
    validate_jobid(job_id)
    apikey = find_api_key()
    for item in fetch_log_for_job(apikey, job_id):
        click.echo(item)


def fetch_log_for_job(apikey, job_id):
    hc = HubstorageClient(auth=apikey)
    job = hc.get_job(job_id)
    if not job.metadata:
        raise ClickException('Job {} doesn\'t exist'.format(job_id))
    return job.logs.iter_values()
