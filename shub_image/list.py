import json

import click
import requests
from six.moves.urllib.parse import urljoin

from shub import exceptions as shub_exceptions
from shub.deploy import list_targets
from shub_image import utils


SETTING_TYPES = ['project_settings',
                 'organization_settings',
                 'enabled_addons']

SHORT_HELP = 'List spiders.'

HELP = """
List command tries to run your image locally and get a spiders list.

Internally, this command is a simple wrapper to `docker run` and uses
docker daemon on your system to run a new container using your image.
Before creating the container, there's a Dash call to get your project
settings to get your spiders list properly (respecting SPIDERS_MODULE
setting, etc).

Image should be set via scrapinghub.yml, section "images". If version is not
provided, the tool uses VCS-based stamp over project directory (the same as
shub utils itself).
"""


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
@click.option("-l", "--list-targets", help="list available targets",
              is_flag=True, is_eager=True, expose_value=False,
              callback=list_targets)
@click.option("-d", "--debug", help="debug mode", is_flag=True)
@click.option("-s", "--silent", help="silent mode", is_flag=True)
@click.option("--version", help="release version")
def cli(target, debug, silent, version):
    list_cmd_full(target, silent, version)


def list_cmd_full(target, silent, version):
    config = utils.load_release_config()
    image = config.get_image(target)
    version = version or config.get_version()
    image_name = utils.format_image_name(image, version)
    project, endpoint, apikey = None, None, None
    try:
        project, endpoint, apikey = config.get_target(target)
    except shub_exceptions.BadParameterException as exc:
        if 'Could not find target' not in exc.message:
            raise
        if not silent:
            click.echo(
                "Not found project for target {}, "
                "not getting project settings from Dash.".format(target))
    spiders = list_cmd(image_name, project, endpoint, apikey)
    for spider in spiders:
        click.echo(spider)


def list_cmd(image_name, project, endpoint, apikey):
    """Short version of list cmd to use with deploy cmd."""

    settings = {}
    if project:
        settings = _get_project_settings(project, endpoint, apikey)

    # Run a local docker container to run list-spiders cmd
    status_code, logs = _run_list_cmd(project, image_name, settings)
    if status_code != 0:
        click.echo(logs)
        raise shub_exceptions.ShubException(
            'Container with list cmd exited with code %s' % status_code)

    spiders = utils.valid_spiders(logs)
    return spiders


def _get_project_settings(project, endpoint, apikey):
    utils.debug_log('Getting settings for {} project:'.format(project))
    req = requests.get(
        urljoin(endpoint, '/api/settings/get.json'),
        params={'project': project},
        auth=(apikey, ''),
        timeout=300,
        allow_redirects=False
    )
    req.raise_for_status()
    utils.debug_log("Response: {}".format(req.json()))
    return {k: v for k, v in req.json().items() if k in SETTING_TYPES}


def _run_list_cmd(project, image_name, project_settings):
    """Run `scrapy list` command inside the image container."""

    client = utils.get_docker_client()
    # FIXME we should pass some value for SCRAPY_PROJECT_ID anyway
    # to handle `scrapy list` cmd properly via sh_scrapy entrypoint
    project = str(project) if project else ''
    job_settings = json.dumps(project_settings)
    container = client.create_container(
        image=image_name,
        command=['list-spiders'],
        environment={'SCRAPY_PROJECT_ID': project,
                     'JOB_SETTINGS': job_settings})
    if 'Id' not in container:
        raise shub_exceptions.ShubException(
            "Create container error:\n %s" % container)

    client.start(container)
    statuscode = client.wait(container=container['Id'])

    return statuscode, client.logs(
            container=container['Id'],
            stdout=True, stderr=True if statuscode else False,
            stream=False, timestamps=False)
