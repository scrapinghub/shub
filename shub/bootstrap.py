from __future__ import absolute_import

import click
import requests
import yaml
from click.formatting import HelpFormatter

from shub.exceptions import RemoteErrorException


EXAMPLE_REPO = "scrapinghub/custom-images-examples"
AVAILABLE_PROJECTS_URL = (
    "https://raw.githubusercontent.com/%s/master/bootstrap_projects.yml"
    "" % EXAMPLE_REPO)

HELP = """
Through custom images, Scrapinghub allows you to run crawlers written in any
language you want. To get you started, we prepared a few examples projects in
different programming languages and frameworks. You can find them in our custom
images repository at:

    https://github.com/scrapinghub/custom-images-examples

The 'shub bootstrap' command clones an example project to the current directory
so that you can start hacking right away.

Run

    shub bootstrap -l

to get a list of all available example projects, then run

    shub bootstrap PROJECTNAME

to clone it.
"""

SHORT_HELP = "Clone custom image example project"


def list_projects_callback(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    projects = get_available_projects()
    list_projects(projects)
    ctx.exit()


@click.command(help=HELP, short_help=SHORT_HELP)
@click.option('-l', '--list', 'list_projects', help='list available projects',
              is_flag=True, callback=list_projects_callback,
              expose_value=False, is_eager=True)
def cli():
    pass


def get_available_projects():
    try:
        resp = requests.get(AVAILABLE_PROJECTS_URL)
        resp.raise_for_status()
    except (requests.HTTPError, requests.ConnectionError) as e:
        raise RemoteErrorException(
            "There was an error while getting the list of available projects "
            "from GitHub: %s.\n\nPlease check your connection or go to\n  %s\n"
            "to browse the custom image examples manually."
            "" % (e, "https://github.com/%s" % EXAMPLE_REPO))
    return yaml.safe_load(resp.text)


def list_projects(projects):
    formatter = HelpFormatter()
    with formatter.section("Available projects"):
        formatter.write_dl(
            sorted(
                [(name, info['description'])
                 for name, info in projects.items()],
                key=lambda x: x[0]))
    click.echo(formatter.getvalue().strip())
