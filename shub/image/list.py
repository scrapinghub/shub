import json

import click
import docker
import requests
import six
from six import binary_type
from six import string_types
from six.moves.urllib.parse import urljoin

from shub.exceptions import ShubException
from shub.config import load_shub_config, list_targets_callback
from shub.image import utils


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
@click.option("-l", "--list-targets", is_flag=True, is_eager=True,
              expose_value=False, callback=list_targets_callback,
              help="List available project names defined in your config")
@click.option("-d", "--debug", help="debug mode", is_flag=True,
              callback=utils.deprecate_debug_parameter)
@click.option("-v", "--verbose", is_flag=True, help="stream logs to console")
@click.option("-s", "--silent", is_flag=True,
              help="don't warn if Dash project is not defined in config")
@click.option("-V", "--version", help="release version")
def cli(target, debug, verbose, silent, version):
    list_cmd_full(target, silent, version)


def list_cmd_full(target, silent, version):
    config = load_shub_config()
    image = config.get_image(target)
    version = version or config.get_version()
    image_name = utils.format_image_name(image, version)
    target_conf = config.get_target_conf(target)
    metadata = list_cmd(image_name,
                        target_conf.project_id,
                        target_conf.endpoint,
                        target_conf.apikey)
    for spider in metadata.get('spiders', []):
        click.echo(spider)


def list_cmd(image_name, project, endpoint, apikey):
    """Short version of list cmd to use with deploy cmd."""
    settings = _get_project_settings(project, endpoint, apikey)
    environment = {'JOB_SETTINGS': json.dumps(settings)}
    exit_code, logs = _run_cmd_in_docker_container(
            image_name, 'shub-image-info', environment)
    if exit_code == 0:
        return _extract_metadata_from_image_info_output(logs)
    # shub-image-info command not found, fallback to list-spiders
    elif exit_code == 127:
        # FIXME we should pass some value for SCRAPY_PROJECT_ID anyway
        # to handle `scrapy list` cmd properly via sh_scrapy entrypoint
        # environment['SCRAPY_PROJECT_ID'] = str(project) if project else ''
        exit_code, logs = _run_cmd_in_docker_container(
            image_name, 'list-spiders', environment)
        if exit_code != 0:
            click.echo(logs)
            raise ShubException('Container with list cmd exited with code %s' % exit_code)
        logs = logs.decode('utf-8') if isinstance(logs, binary_type) else logs
        return {
            'project_type': 'scrapy',
            'spiders': utils.valid_spiders(logs.splitlines()),
        }
    else:
        click.echo(logs)
        raise ShubException(
            'Container with shub-image-info cmd exited with code %s' % exit_code)


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


def _run_cmd_in_docker_container(image_name, command, environment):
    """Run a command inside the image container."""
    client = utils.get_docker_client()
    container = client.create_container(
        image=image_name,
        command=[command],
        environment=environment,
    )
    if 'Id' not in container:
        raise ShubException("Create container error:\n %s" % container)
    try:
        client.start(container)
    except docker.errors.APIError as e:
        explanation = e.explanation or ''
        if 'executable file not found' in explanation:
            # docker.errors.APIError: 500 Server Error:
            # Internal Server Error ("Cannot start container xxx:
            # [8] System error: exec: "shub-image-info":
            # executable file not found in $PATH")
            return 127, None
        raise
    statuscode = client.wait(container=container['Id'])
    return statuscode, client.logs(
            container=container['Id'],
            stdout=True, stderr=True if statuscode else False,
            stream=False, timestamps=False)


def _extract_metadata_from_image_info_output(output):
    """Extract and validate spiders list from `shub-image-info` output."""

    def raise_shub_image_info_error(error):
        """Helper to raise ShubException with prefix and output"""
        msg = "shub-image-info: {} \n[output '{}']".format(error, output)
        raise ShubException(msg)

    try:
        if six.PY2:
            metadata = json.loads(output)
        else:
            if isinstance(output, str):
                metadata = json.loads(output)
            else:
                metadata = json.loads(output.decode('utf-8'))
        project_type = metadata.get('project_type')
    except (AttributeError, ValueError):
        raise_shub_image_info_error('output is not a valid JSON dict')
    if not isinstance(project_type, string_types):
        raise_shub_image_info_error('"project_type" key is required and must be a string')

    spiders_list = metadata.get('spiders')
    if not isinstance(spiders_list, list):
        raise_shub_image_info_error('"spiders" key is required and must be a list')
    spiders, scripts = [], []
    for name in spiders_list:
        if not (name and isinstance(name, string_types)):
            raise_shub_image_info_error("spider name can't be empty or non-string")
        if project_type == 'scrapy' and name.startswith('py:'):
            scripts.append(name[3:])
        else:
            spiders.append(name)
    return {
        'project_type': project_type,
        'spiders': utils.valid_spiders(spiders),
        'scripts': utils.valid_spiders(scripts),
    }
