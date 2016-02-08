import os
from six.moves.urllib.parse import urljoin
import click
import requests

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
@click.argument("target", required=False, default='default')
@click.argument("new_project", required=True)
def cli(target, new_project):
    project, endpoint, apikey = get_target(target)
    sync_project(project, endpoint, apikey, int(new_project))


def sync_project(project, endpoint, apikey, new_project):
    egg_versions = get_eggs_versions(project, endpoint, apikey)
    destfile = 'eggs-%s.zip' % project
    fetch_eggs(project, endpoint, apikey, destfile)
    decompress_egg_files()
    destdir = "eggs-{}".format(project)
    for egg_name in os.listdir(destdir):
        if egg_name == "__main__.egg":
            continue
        name = egg_name.partition(".egg")[0]
        version = egg_versions[name]
        egg_path = os.path.join(destdir, egg_name)
        egg_info = (egg_name, egg_path)
        _deploy_dependency_egg(new_project, endpoint, apikey, name=name, version=version,
                               egg_info=egg_info)



def get_eggs_versions(project, endpoint, apikey):
    click.echo('Getting eggs list from project {}...'.format(project))
    list_endpoint = urljoin(endpoint, "eggs/list.json")
    response = requests.get(urljoin(list_endpoint, "?project={}".format(project)),
                            auth=(apikey, ''))
    response.raise_for_status()
    obj = response.json()
    return {x['name']: x['version'] for x in obj['eggs']}
