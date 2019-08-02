from __future__ import absolute_import

import click

from scrapinghub import ScrapinghubAPIError
from scrapinghub.client.utils import parse_job_key

from shub.utils import get_scrapinghub_client_from_config
from shub.config import get_target_conf
from shub.exceptions import (
    ShubException,
    BadParameterException,
    SubcommandException,
)


HELP = """
Cancel multiple jobs from Scrapy Cloud.

The cancel command expects the project ID (target) followed by
the pair containing the spider ID and Job ID:

    shub cancel 12345 1/1 1/2 1/3

If the project ID is not defined it is going to use the default
project (as defined in scrapinghub.yml):

    shub cancel 1/1 1/2 1/3

The cancel command requires a confirmation that could be skipped
with the flag --force/-f:

    shub cancel --force 1/1 1/2 1/3
"""


SHORT_HELP = "Cancel multiple jobs from Scrapy Cloud"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target_or_key")
@click.argument("keys", nargs=-1)
@click.option('--force', '-f', is_flag=True,
              help='It ignores the confirmation prompt')
def cli(target_or_key, keys, force):
    # target_or_key contains a target or just another job key
    if "/" in target_or_key:
        keys = (target_or_key,) + keys
        target = "default"
    else:
        target = target_or_key

    targetconf = get_target_conf(target)
    project_id = targetconf.project_id
    client = get_scrapinghub_client_from_config(targetconf)
    project = client.get_project(project_id)

    try:
        job_keys = [validate_job_key(project_id, key) for key in keys]
    except (BadParameterException, SubcommandException) as err:
        click.echo('Error during keys validation: %s' % str(err))
        exit(1)

    if not force:
        jobs_str = ", ".join([str(job) for job in job_keys])
        click.confirm(
            'Do you want to cancel these %s jobs? \n\n%s \n\nconfirm?'
            % (len(job_keys), jobs_str),
            abort=True
        )

    try:
        output = project.jobs.cancel(
            keys=[str(job) for job in job_keys]
        )
    except (ValueError, ScrapinghubAPIError) as err:
        raise ShubException(str(err))

    click.echo(output)


def validate_job_key(project_id, short_key):
    job_key = "%s/%s" % (project_id, short_key)

    if len(short_key.split("/")) != 2:
        raise BadParameterException(
            "keys must be defined as <spider_id>/<job_id>"
        )

    try:
        return parse_job_key(job_key)
    except ValueError as err:
        raise BadParameterException(str(err))
    except Exception as err:
        raise SubcommandException(str(err))
