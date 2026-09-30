import click
import requests

from shub.exceptions import RemoteErrorException
from shub.utils import _fetch_scrapy_stack_releases, _format_scrapy_stack


HELP = """
List the Scrapy Cloud stacks you can set as the stack of your project in
scrapinghub.yml, newest first: the latest release of each Scrapy version, or
every release with --all.
"""

SHORT_HELP = "List available Scrapy Cloud stacks"

TAGS_URL = "https://github.com/scrapinghub/scrapinghub-stack-scrapy/tags"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.option('-a', '--all', 'list_all', is_flag=True,
              help="List every release of each Scrapy version.")
def cli(list_all):
    try:
        releases = _fetch_scrapy_stack_releases()
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        raise RemoteErrorException(
            f"Could not fetch the list of stacks ({e}), see {TAGS_URL}")
    releases.sort(reverse=True)
    if not list_all:
        latest = {}
        for release in releases:
            latest.setdefault(release[:2], release)
        releases = list(latest.values())
    for release in releases:
        click.echo(_format_scrapy_stack(release))
