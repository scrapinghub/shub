import os
import re
import json
import click

from shub import exceptions as shub_exceptions
from shub.deploy import list_targets
from shub.deploy import _create_default_setup_py
from shub.utils import closest_file, get_config
from shub_image import utils


SHORT_HELP = 'Build release image.'

HELP = """
Build command uses your Dockerfile to build an image and tag it properly.

Internally, this command is a simple wrapper to `docker build` and uses
docker daemon on your system to build an image. Also it can generate
project version for you, and locate root project directory by itself.

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
@click.option("--version", help="release version")
def cli(target, debug, version):
    build_cmd(target, version)


def build_cmd(target, version):
    client = utils.get_docker_client()
    project_dir = utils.get_project_dir()
    config = utils.load_release_config()
    image = config.get_image(target)
    _create_setup_py_if_not_exists()
    image_name = utils.format_image_name(image, version)
    if not os.path.exists(os.path.join(project_dir, 'Dockerfile')):
        raise shub_exceptions.BadParameterException(
            'Dockerfile is not found, please use shub-image init cmd')
    is_built = False
    for line in client.build(path=project_dir, tag=image_name):
        data = json.loads(line)
        if 'stream' in data:
            utils.debug_log("{}".format(data['stream'][:-1]))
            is_built = re.search(
                r'Successfully built ([0-9a-f]+)', data['stream'])
        elif 'error' in data:
            click.echo("Error {}:\n{}".format(
                data['error'], data['errorDetail']))
    if not is_built:
        raise shub_exceptions.RemoteErrorException(
            "Build image operation failed")
    click.echo("The image {} build is completed.".format(image_name))


def _create_setup_py_if_not_exists():
    closest = closest_file('scrapy.cfg')
    # create default setup.py only if scrapy.cfg is found, otherwise
    # consider it as a non-scrapy/non-python project. FIXME do we need
    # some warning here in a case if user forgot to create scrapy.cfg?
    if not closest:
        return
    with utils.remember_cwd():
        os.chdir(os.path.dirname(closest))
        if not os.path.exists('setup.py'):
            settings = get_config().get('settings', 'default')
            _create_default_setup_py(settings=settings)
