from __future__ import absolute_import

import re

import click
import requests

from shub.exceptions import RemoteErrorException


RELEASES_WEB_URL = "https://github.com/{repo}/releases"
TAGS_API_URL = "https://api.github.com/repos/{repo}/tags"
STACK_REPOSITORIES = [
    # (stack type, prefix, repository)
    ('Scrapy', 'scrapy', 'scrapinghub/scrapinghub-stack-scrapy'),
    ('Portia', 'portia', 'scrapinghub/scrapinghub-stack-portia'),
]

HELP = """
List the available stacks that you can run your project in. Use --all to
include regular releases.

\b
See
https://helpdesk.scrapinghub.com/support/solutions/articles/22000200402-scrapy-cloud-stacks
for a general introduction to stacks, and
https://shub.readthedocs.io/en/stable/configuration.html#choosing-a-scrapy-cloud-stack
for information on how to configure a stack for your project.
"""

SHORT_HELP = "List available stacks"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.option('-a', '--all', 'print_all', help='include regular releases',
              is_flag=True)
def cli(print_all):
    for i, (stack_type, prefix, repo) in enumerate(STACK_REPOSITORIES):
        if i:
            click.echo('')
        tags = get_repository_tags(repo)
        click.echo("%s stacks:" % stack_type)
        click.echo(_format_list(
            prefix + ':' + tag
            for tag in filter_tags(tags, include_regular=print_all)))


def _format_list(l):
    return '\n'.join('  %s' % x for x in l)


def get_repository_tags(repo):
    try:
        resp = requests.get(TAGS_API_URL.format(repo=repo))
        resp.raise_for_status()
        tags = resp.json()
        while 'next' in resp.links:
            resp = requests.get(resp.links['next']['url'])
            resp.raise_for_status()
            tags.extend(resp.json())
    except (requests.HTTPError, requests.ConnectionError) as e:
        if isinstance(e, requests.HTTPError):
            msg = resp.json()['message']
        else:
            msg = e.args[0]
        repo_url_list = _format_list(
            '%s: %s' % (desc, RELEASES_WEB_URL.format(repo=repo))
            for desc, _, repo in STACK_REPOSITORIES)
        raise RemoteErrorException(
            "Error while retrieving the list of stacks from GitHub: %s\n\n"
            "Please visit the following URLs to see the available stacks: \n%s"
            "" % (msg, repo_url_list))
    else:
        return [tag['name'] for tag in tags]


def _is_regular_release(tag):
    return re.search('\d{8}', tag)


def filter_tags(tags, include_regular=False):
    if include_regular:
        return tags
    return [t for t in tags if not _is_regular_release(t)]
