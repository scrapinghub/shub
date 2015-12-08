from __future__ import absolute_import
import click
import requests
from click import ClickException

from shub.auth import find_api_key
from shub.click_utils import log
from shub.exceptions import AuthException


@click.command(help="Download a project's eggs from the Scrapy Cloud")
@click.argument("project_id", required=True)
def cli(project_id):
    api_key = find_api_key()
    destfile = 'eggs-%s.zip' % project_id
    fetch_eggs(project_id, api_key, destfile)


def fetch_eggs(project_id, api_key, destfile):
    auth = (api_key, '')
    url = "https://dash.scrapinghub.com/api/eggs/bundle.zip?project=%s" % project_id
    rsp = requests.get(url=url, auth=auth, stream=True, timeout=300)

    _assert_response_is_valid(rsp)

    log("Downloading eggs to %s" % destfile)

    with open(destfile, 'wb') as f:
        for chunk in rsp.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                f.flush()


def _assert_response_is_valid(rsp):
    if rsp.status_code == 403:
        raise AuthException()
    elif rsp.status_code != 200:
        msg = 'Eggs could not be fetched. Status: %d' % rsp.status_code
        raise ClickException(msg)
