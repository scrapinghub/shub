import sys
import click

from shub.utils import find_api_key, is_valid_projectid
from shub.hubstorage import HubStorageQueryJobs as Query

@click.command(help='Get jobs of a given project on Scrapy Cloud')
@click.pass_context
@click.argument('project_id')
@click.option('-t', '--output-format', help='the format of the data to be printed', required=False, type=click.Choice(Query.get_allowed_formats().keys()), default='jl')
@click.option('-o', '--output-file', help='the file to dump the downloaded data into', required=False, type=click.File('a+'), default=sys.stdout)
def cli(context, project_id, output_file, output_format):
    if not is_valid_projectid(project_id):
        context.fail('Invalid Project ID')
    key = find_api_key()
    if not key:
        context.fail('Scrapinghub API key not found: \
                      please, run \'scrapy login\' first')
    query = Query(
        key=key,
        output=output_file,
        output_format=output_format,
        project_id=project_id)
    query.download_and_write_data()
