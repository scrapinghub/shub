import os
from urllib.parse import urljoin
from tempfile import mkdtemp
import click
import requests
from shutil import rmtree

from shub.config import get_target_conf
from shub.fetch_eggs import fetch_eggs
from shub.utils import decompress_egg_files, _deploy_dependency_egg

SHORT_HELP = "Sync eggs from one project with other project"

HELP = SHORT_HELP + """

Fetch all eggs from one project and upload them to other project. This allows
you to easily clone requirements from an old project into a new one."""


@click.command(help=HELP, short_help=SHORT_HELP)
@click.option("--source_project",
              prompt="From which projects should I download eggs?")
@click.option("--new_project",
              prompt="To which project should I upload eggs?")
@click.option("-m", "--copy-main", default=False, is_flag=True,
              help="copy main Scrapy project egg")
def cli(source_project, new_project, copy_main):
    source = get_target_conf(source_project)
    target = get_target_conf(new_project)
    copy_eggs(source.project_id, source.endpoint, source.apikey,
              target.project_id, target.endpoint, target.apikey,
              copy_main)


def copy_eggs(project, endpoint, apikey, new_project, new_endpoint, new_apikey,
              copy_main):
    egg_versions = get_eggs_versions(project, endpoint, apikey)
    temp_dir = mkdtemp()
    destfile = os.path.join(temp_dir, 'eggs-%s.zip' % project)
    fetch_eggs(project, endpoint, apikey, destfile)
    # Decompress project bundle (so temp_dir will contain all project eggs)
    decompress_egg_files(directory=temp_dir)
    destdir = os.path.join(temp_dir, f"eggs-{project}")
    for egg_name in os.listdir(destdir):
        if egg_name == "__main__.egg" and not copy_main:
            continue
        name = egg_name.partition(".egg")[0]
        try:
            version = egg_versions[name]
        except KeyError:
            click.secho(
                "WARNING: The following egg belongs to a Dash Addon: %s. "
                "Please manually enable the corresponding Addon in the target "
                "project." % name,
                fg='yellow',
                bold=True,
            )
            continue
        egg_path = os.path.join(destdir, egg_name)
        egg_info = (egg_name, egg_path)
        _deploy_dependency_egg(new_project, new_endpoint, new_apikey,
                               name=name, version=version, egg_info=egg_info)
    rmtree(temp_dir)


def get_eggs_versions(project, endpoint, apikey):
    click.echo(f'Getting eggs list from project {project}...')
    list_endpoint = urljoin(endpoint, "eggs/list.json")
    response = requests.get(list_endpoint, params={"project": project},
                            auth=(apikey, ''))
    response.raise_for_status()
    obj = response.json()
    return {x['name']: x['version'] for x in obj['eggs']}
