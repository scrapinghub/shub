from datetime import datetime

import click
from dateparser import parse
from scrapinghub import ScrapinghubClient


HELP = """
Given a project key and part of an url, fetch job ids from Scrapy Cloud.

This is useful when you want to find a job in an efficient way starting from
an url.

The project key and an url (or part of it). The matching is case sensitive!

    shub search 123456 "B07F3NG1234"

You can provide other parameters to narrow down the search significantly such
as the spider name and the date interval to search for. Or both! The default
is to search only the last 6 months.
    
    shub search 123456 "B07F3NG1234" --spider="amazon"

    shub search 123456 "B07F3NG1234" --start_date="last week" --end_date="2 days ago" 
"""

SHORT_HELP = "Fetch job ids from Scrapy Cloud based on urls"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('project_key')
@click.argument('url_content')
@click.option(
    '--start_date',
    default='6 months ago',
    help='date to start searching from, defaults to 6 months ago'
)
@click.option('--end_date', default='now', help='date to end the search')
@click.option('-s', '--spider', help='the spider to search')
def cli(project_key, url_content, start_date, end_date, spider):
    def date_string_to_seconds(date):
        return int((parse(date) - datetime(1970, 1, 1)).total_seconds() * 1000)

    start_time = date_string_to_seconds(start_date)
    end_time = date_string_to_seconds(end_date)

    project = ScrapinghubClient().get_project(project_key)

    jobs = project.jobs.iter(startts=start_time, endts=end_time, spider=spider)
    for job_dict in jobs:
        job = project.jobs.get(job_dict['key'])
        for req in job.requests.iter(filter=[('url', 'contains', [url_content])]):
            click.echo(job_dict['key'])
            break

