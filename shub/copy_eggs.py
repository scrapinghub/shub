from __future__ import absolute_import
import os
from six.moves.urllib.parse import urljoin
from tempfile import mkdtemp
import click
import requests
from shutil import rmtree

from shub.config import get_target
from shub.fetch_eggs import fetch_eggs
from shub.utils import decompress_egg_files, _deploy_dependency_egg

SHORT_HELP = "Sync eggs from one project with other project"

HELP = SHORT_HELP + """

Fetch all eggs from one project and upload them to other project. This allows
you to easily clone requirements from old project if you set up some new
project in dash.
"""


@click.command(help=HELP, short_help=SHORT_HELP)
@click.option("--source_project", prompt="From which projects should I download eggs?")
@click.option("--new_project", prompt="To which project should I upload eggs?")
@click.option("-m", "--copy-main", default=False, is_flag=True, help="copy main Scrapy project egg")
def cli(source_project, new_project, copy_main):
    project, endpoint, apikey = get_target(source_project)
    new_project, new_endpoint, new_apikey = get_target(new_project)
    copy_eggs(project, endpoint, apikey, new_project, new_endpoint, new_apikey, copy_main)


def copy_eggs(project, endpoint, apikey, new_project, new_endpoint, new_apikey, copy_main):

    egg_versions = get_eggs_versions(project, endpoint, apikey)
    temp_dir = mkdtemp()
    destfile = os.path.join(temp_dir, 'eggs-%s.zip' % project)
    fetch_eggs(project, endpoint, apikey, destfile)

    # this will decompress egg containing other eggs, not eggs from source project
    decompress_egg_files(directory=temp_dir)
    destdir = os.path.join(temp_dir, "eggs-{}".format(project))
    for egg_name in os.listdir(destdir):
        if egg_name == "__main__.egg" and not copy_main:
            continue
        name = egg_name.partition(".egg")[0]
        version = egg_versions[name]
        egg_path = os.path.join(destdir, egg_name)
        egg_info = (egg_name, egg_path)
        _deploy_dependency_egg(new_project, new_endpoint, new_apikey, name=name, version=version,
                               egg_info=egg_info)

    # remove temporary directory
    rmtree(temp_dir)


def get_eggs_versions(project, endpoint, apikey):
    click.echo('Getting eggs list from project {}...'.format(project))
    list_endpoint = urljoin(endpoint, "eggs/list.json")
    response = requests.get(list_endpoint, params={"project": project},
                            auth=(apikey, ''))
    response.raise_for_status()
    obj = response.json()
    return {x['name']: x['version'] for x in obj['eggs']}
