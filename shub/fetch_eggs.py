import click
import requests

from shub.utils import find_api_key
from shub.click_utils import log


@click.command(help="Download a project's eggs from the Scrapy Cloud")
@click.argument("project_id", required=True)
def cli(project_id):
    auth = (find_api_key(), '')
    url = "https://dash.scrapinghub.com/api/eggs/bundle.zip?project=%s" % project_id
    rsp = requests.get(url=url, auth=auth, stream=True, timeout=300)

    destfile = 'eggs-%s.zip' % project_id
    log("Downloading eggs to %s" % destfile)

    with open(destfile, 'wb') as f:
        for chunk in rsp.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                f.flush()
