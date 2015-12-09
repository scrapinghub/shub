import click

from shub.utils import get_job


@click.command(help='Get items of a given job on Scrapy Cloud')
@click.argument('job_id')
def cli(job_id):
    job = get_job(job_id)
    for item in job.items.iter_values():
        click.echo(item)
