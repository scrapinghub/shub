import logging
from datetime import datetime

from shub.utils import job_resource_iter, get_job

import click


HELP = """
Given a job ID, fetch the log of that job from Scrapy Cloud and print it.

A job ID consists of the Scrapinghub project ID, the numerical spider ID, and
the job ID, separated by forward slashes, e.g.:

    shub log 12345/2/15

You can also provide the Scrapinghub job URL instead:

    shub log https://app.scrapinghub.com/p/12345/job/2/15

You can omit the project ID if you have a default target defined in your
scrapinghub.yml:

    shub log 2/15

Or use any target defined in your scrapinghub.yml:

    shub log production/2/15

If the job is still running, you can watch the log as it is being written by
providing the -f flag:

    shub log -f 2/15
"""

SHORT_HELP = "Fetch log from Scrapy Cloud"


class LogIterFunc(object):
    def __init__(self, job, tail):
        logstats = job.logs.stats()
        lines = logstats['totals']['input_values']
        lastline = max(lines - tail, -1)
        if lastline == -1:
            lastline = None
        self._startafter = None if lastline is None else '{}/{}'.format(job.key, lastline)
        self._logs = job.logs

    def __call__(self, startafter=None):
        startafter = startafter or self._startafter
        for item in self._logs.iter_values(startafter=startafter):
            self._startafter = item['_key']
            yield item

@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('job_id')
@click.option('-f', '--follow', help='output new log entries as they are '
              'produced', is_flag=True)
@click.option('-n', '--tail',
              help='Output last N lines. Default: %(default)s', default=50)
def cli(job_id, follow, tail):
    job = get_job(job_id)
    for item in job_resource_iter(job, LogIterFunc(job, tail), follow=follow,
                                  key_func=lambda item: item['_key']):
        click.echo(
            "{} {} {}".format(
                datetime.utcfromtimestamp(item['time']/1000),
                logging.getLevelName(int(item['level'])),
                item['message']
            )
        )
