from datetime import datetime, timezone

import click
import requests
from scrapinghub import ScrapinghubAPIError

from shub import config
from shub.exceptions import BadParameterException, RemoteErrorException
from shub.utils import get_scrapinghub_client_from_config


HELP = """
List the most recent jobs of a project or of a spider on Scrapy Cloud, one
per line, newest first. The first column is the job key, which you can pass
to other commands, e.g. `shub log 12345/2/15`.

By default, the jobs of your default project (as defined in scrapinghub.yml)
are listed:

\b
    shub jobs

You can list the jobs of another project by supplying its ID or a target
defined in scrapinghub.yml:

\b
    shub jobs 12345
    shub jobs production

Or list only the jobs of a spider, by supplying the spider's name, optionally
preceded by a project ID or target and a slash (just like in `shub schedule`):

\b
    shub jobs myspider
    shub jobs 12345/myspider
    shub jobs production/myspider

An argument consisting only of digits is taken as a project ID, and an
argument that is a target defined in scrapinghub.yml is taken as that target.
To list the jobs of a spider whose name is of either kind, add the project
before the slash: `shub jobs default/123`.

Pending, running, and finished jobs are listed; at most --limit of them
(20 by default).

Use --filter KEY=VALUE (repeatable) to narrow down the jobs:

\b
    state=pending|running|finished|deleted  only jobs in that state
    tag=TAG                                 only jobs having that tag
    no-tag=TAG                              only jobs not having that tag
    arg.NAME=VALUE                          only jobs run with that spider
                                            argument

Repeated state or tag filters match jobs that fulfil any of them, while
repeated no-tag and arg.* filters must all be fulfilled. The arg.* filters
are applied by shub, not by Scrapy Cloud, to the (up to 1000) latest jobs,
before --limit is applied.

Use --orderby FIELD[:asc|:desc] to sort the listed jobs (descending, i.e.
largest or newest first, unless :asc is given). FIELD is one of scheduled,
started, finished, items, errors, spider. Scrapy Cloud cannot sort jobs, so
only the jobs retrieved by --limit are sorted; to rank all recent jobs, use
a large --limit.
"""

SHORT_HELP = "List the latest jobs of a project or spider"

DEFAULT_LIMIT = 20
MAX_JOBS = 1000  # what Scrapy Cloud returns at most per request
DEFAULT_STATES = ['pending', 'running', 'finished']
STATES = DEFAULT_STATES + ['deleted']
ARG_PREFIX = 'arg.'

# --orderby name -> field of the job summary
ORDER_FIELDS = {
    'scheduled': 'pending_time',
    'started': 'running_time',
    'finished': 'finished_time',
    'items': 'items',
    'errors': 'errors',
    'spider': 'spider',
}
# Counters, which job summaries leave out while they are 0
COUNTERS = ('items', 'errors')

# Extra job metadata requested from Scrapy Cloud when it is needed for
# --filter arg.NAME=VALUE. The list must be complete, since Scrapy Cloud only
# adds a few default fields to the ones requested.
SUMMARY_META = ['spider', 'state', 'close_reason', 'spider_args',
                'pending_time', 'running_time', 'finished_time',
                'items', 'errors']

COLUMNS = ('JOB', 'SPIDER', 'STATE', 'STARTED (UTC)')


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('project_or_spider', required=False)
@click.option('--limit', type=click.IntRange(min=1),
              default=DEFAULT_LIMIT, show_default=True,
              help='Maximum number of jobs to list')
@click.option('--filter', 'filters', multiple=True, metavar='KEY=VALUE',
              help='Only list jobs matching KEY=VALUE (state, tag, no-tag, '
                   'arg.NAME); can be repeated')
@click.option('--orderby', metavar='FIELD[:asc|:desc]',
              help='Sort the listed jobs by scheduled, started, finished, '
                   'items, errors, or spider')
def cli(project_or_spider, limit, filters, orderby):
    target, spider = resolve_target(project_or_spider)
    params, spider_args = parse_filters(filters)
    order_field, descending = parse_orderby(orderby)
    targetconf = config.get_target_conf(target)
    client = get_scrapinghub_client_from_config(targetconf)
    try:
        project = client.get_project(targetconf.project_id)
        if spider:
            project.spiders.get(spider)  # fail early if there is no such spider
        kwargs = dict(params, state=params.get('state') or DEFAULT_STATES)
        if spider:
            kwargs['spider'] = spider
        if spider_args:
            # Filtered below, so --limit cannot be applied by Scrapy Cloud
            kwargs.update(meta=SUMMARY_META, count=MAX_JOBS)
        else:
            kwargs['count'] = limit
        jobs = list(project.jobs.iter(**kwargs))
    except (ScrapinghubAPIError, requests.RequestException) as e:
        raise RemoteErrorException(str(e))
    if spider_args:
        jobs = [job for job in jobs if matches_args(job, spider_args)]
        jobs = jobs[:limit]
    if order_field:
        jobs = sort_jobs(jobs, order_field, descending)
    if not jobs:
        click.echo("No jobs found.")
        return
    for line in format_jobs(jobs):
        click.echo(line)


def resolve_target(argument):
    """Return (target, spider name or None) for the command's argument."""
    if not argument:
        return 'default', None
    if '/' in argument:
        target, spider = argument.rsplit('/', 1)
        return target or 'default', spider or None
    if argument.isdigit() or argument in config.load_shub_config().projects:
        return argument, None
    return 'default', argument


def parse_filters(filters):
    """Return (parameters for ``project.jobs.iter``, spider arguments)."""
    params = {}
    spider_args = {}
    keys = {'state': 'state', 'tag': 'has_tag', 'no-tag': 'lacks_tag'}
    for item in filters:
        key, sep, value = item.partition('=')
        if not sep or not value:
            raise BadParameterException(
                "%r is not of the form KEY=VALUE" % item, param_hint='--filter')
        if key.startswith(ARG_PREFIX) and len(key) > len(ARG_PREFIX):
            spider_args[key[len(ARG_PREFIX):]] = value
        elif key in keys:
            if key == 'state' and value not in STATES:
                raise BadParameterException(
                    "state must be one of %s" % ', '.join(STATES),
                    param_hint='--filter')
            params.setdefault(keys[key], []).append(value)
        else:
            raise BadParameterException(
                "unknown filter %r, use state, tag, no-tag, or arg.NAME" % key,
                param_hint='--filter')
    return params, spider_args


def parse_orderby(orderby):
    """Return (job summary field or None, descending)."""
    if not orderby:
        return None, True
    name, _, direction = orderby.partition(':')
    if name not in ORDER_FIELDS or direction not in ('', 'asc', 'desc'):
        raise BadParameterException(
            "use FIELD[:asc|:desc], where FIELD is one of %s"
            % ', '.join(ORDER_FIELDS), param_hint='--orderby')
    return ORDER_FIELDS[name], direction != 'asc'


def matches_args(job, spider_args):
    job_args = job.get('spider_args') or {}
    return all(k in job_args and str(job_args[k]) == v
               for k, v in spider_args.items())


def sort_jobs(jobs, field, descending):
    if field in COUNTERS:
        return sorted(jobs, key=lambda job: job.get(field) or 0,
                      reverse=descending)
    # Jobs lacking the field (e.g. not started yet) always go last
    have = [job for job in jobs if job.get(field) is not None]
    lack = [job for job in jobs if job.get(field) is None]
    return sorted(have, key=lambda job: job[field], reverse=descending) + lack


def format_time(timestamp):
    if not timestamp:
        return '-'
    dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def format_jobs(jobs):
    rows = [COLUMNS]
    for job in jobs:
        state = job.get('state') or '-'
        if job.get('close_reason'):
            state = "%s (%s)" % (state, job['close_reason'])
        rows.append((job['key'], job.get('spider') or '-', state,
                     format_time(job.get('running_time'))))
    widths = [max(len(row[i]) for row in rows) for i in range(len(COLUMNS))]
    for row in rows:
        yield '  '.join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip()
