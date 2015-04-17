import sys
import click

from shub.utils import find_api_key, is_valid_jobid
from shub.hubstorage import HubStorageQueryRequests as Query

@click.command(help='Get requests information of a given job on Scrapy Cloud')
@click.pass_context
@click.argument('job_id')
@click.option('-t', '--output-format', help='the format of the data to be printed', required=False, type=click.Choice(Query.get_allowed_formats().keys()), default='jl')
@click.option('-o', '--output-file', help='the file to dump the downloaded data into', required=False, type=click.File('a+'), default=sys.stdout)
def cli(context, job_id, output_file, output_format):
    if not is_valid_jobid(job_id):
        context.fail('Invalid Job ID')
    key = find_api_key()
    if not key:
        context.fail('Scrapinghub API key not found: \
                      please, run \'scrapy login\' first')
    query = Query(
        key=key,
        output=output_file,
        output_format=output_format,
        job_id=job_id)
    query.download_and_write_data()
