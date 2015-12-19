import click

from shub.utils import get_job


@click.command(help='Get requests made for a given job on Scrapy Cloud')
@click.argument('job_id')
def cli(job_id):
    job = get_job(job_id)
    for item in job.requests.iter_json():
        click.echo(item)
