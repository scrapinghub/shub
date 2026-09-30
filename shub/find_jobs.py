import time

import click

from shub.config import get_target_conf
from shub.exceptions import BadParameterException
from shub.utils import get_scrapinghub_client_from_config


HELP = """
Find finished jobs of a Scrapy Cloud project with at least one request, item or
log entry matching the given filters, and output their IDs as they are found.

Filters are JSON lists with a field name, an operator and a list of values.
For example, to find jobs of the "amazon" spider that requested a URL
containing "/dp/B0":

    shub find-jobs --spider amazon --filter '["url", "contains", ["/dp/B0"]]'

To find jobs with errors in their log since a given date, in the project of
the "production" target of your scrapinghub.yml:

    shub find-jobs production --since 2026-09-01 --in logs \\
        --filter '["level", ">=", [40]]'

Jobs are checked one at a time, newest first, with a delay between them to
keep the load on Scrapy Cloud low, and up to --max-jobs jobs are checked.
Narrow the search with --spider, --since and --until to check fewer jobs.
"""

SHORT_HELP = "Find jobs with matching requests, items or log entries"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('target', required=False, default='default')
@click.option('--filter', 'filters', multiple=True, required=True,
              help='filter that a request, item or log entry must match; '
                   'repeat to require several')
@click.option('--in', 'resource', default='requests', show_default=True,
              type=click.Choice(['requests', 'items', 'logs']),
              help='job data to apply the filters to')
@click.option('--spider', help='only check jobs of this spider')
@click.option('--since', type=click.DateTime(),
              help='only check jobs finished at or after this time')
@click.option('--until', type=click.DateTime(),
              help='only check jobs finished before this time')
@click.option('--max-jobs', default=100, show_default=True,
              type=click.IntRange(min=1),
              help='maximum number of jobs to check')
@click.option('--delay', default=1.0, show_default=True,
              type=click.FloatRange(min=0),
              help='seconds to wait between jobs')
def cli(target, filters, resource, spider, since, until, max_jobs, delay):
    if not (spider or since or until):
        raise BadParameterException(
            "Use --spider, --since or --until to narrow the search.")
    targetconf = get_target_conf(target)
    client = get_scrapinghub_client_from_config(targetconf)
    project = client.get_project(targetconf.project_id)
    jobs = project.jobs.iter(
        spider=spider,
        startts=_timestamp_ms(since),
        endts=_timestamp_ms(until),
        count=max_jobs + 1,
    )
    for index, summary in enumerate(jobs):
        if index == max_jobs:
            click.echo(f"Stopped after checking {max_jobs} jobs, use "
                       f"--max-jobs to check more.", err=True)
            break
        if index:
            time.sleep(delay)
        job = client.get_job(summary['key'])
        matches = getattr(job, resource).iter(count=1, filter=list(filters))
        if next(iter(matches), None) is not None:
            click.echo(summary['key'])


def _timestamp_ms(value):
    return None if value is None else int(value.timestamp() * 1000)
