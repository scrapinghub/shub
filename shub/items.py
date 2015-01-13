import sys
import click

from shub.utils import find_api_key, is_valid_jobid
from shub.hubstorage import HubStorageQueryItems as Query

@click.command(help='Get items of a given job on Scrapy Cloud')
@click.pass_context
@click.argument('job_id')
@click.option('-t', '--output-format', help='the format of the data to be printed', required=False, type=click.Choice(Query.get_allowed_formats()), default='jl')
@click.option('-o', '--output-file', help='the file to dump the downloaded data into', required=False, type=click.File('a+'), default=sys.stdout)
@click.option('-f', '--csv-fields', help='the fields to get (for -t csv). Should be separated by commas', required=False, type=click.STRING)
def cli(context, job_id, output_file, output_format, csv_fields):
    if output_format == 'csv' and not csv_fields:
        context.fail('You must specify -f (--csv-fields) to get csv-formatted data')
    if not is_valid_jobid(job_id):
        context.fail('Invalid Job ID')
    key = find_api_key()
    if not key:
        context.fail('Scrapinghub API key not found: \
                      please, run \'scrapy login\' first')
    query = Query(
        key=key,
        job_id=job_id,
        output_format=output_format,
        csv_fields=csv_fields,
        output=output_file)
    query.download_and_write_data()
