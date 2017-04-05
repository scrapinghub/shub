import os
import re
import sys

import click
from tqdm import tqdm

from shub import exceptions as shub_exceptions
from shub.config import load_shub_config
from shub.deploy import list_targets
from shub.image import utils
from shub.image.test import test_cmd


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

BUILD_STEP_REGEX = re.compile(r'Step (\d+)/(\d+) :*')


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
@click.option("-l", "--list-targets", help="list available targets",
              is_flag=True, is_eager=True, expose_value=False,
              callback=list_targets)
@click.option("-d", "--debug", help="debug mode", is_flag=True,
              callback=utils.deprecate_debug_parameter)
@click.option("-v", "--verbose", is_flag=True,
              help="stream build logs to console")
@click.option("-V", "--version", help="release version")
@click.option("-S", "--skip-tests", help="skip testing image", is_flag=True)
def cli(target, debug, verbose, version, skip_tests):
    build_cmd(target, version, skip_tests)


def build_cmd(target, version, skip_tests):
    client = utils.get_docker_client()
    project_dir = utils.get_project_dir()
    config = load_shub_config()
    image = config.get_image(target)
    image_name = utils.format_image_name(image, version)
    if not os.path.exists(os.path.join(project_dir, 'Dockerfile')):
        raise shub_exceptions.BadParameterException(
            "Dockerfile is not found, please use shub image 'init' command")
    bar, is_built = None, False
    verbose = utils.is_verbose()
    for data in client.build(path=project_dir, tag=image_name, decode=True):
        if 'stream' in data:
            if not verbose:
                bar = _create_or_update_progress_bar(bar, data, verbose)
            utils.debug_log("{}".format(data['stream'][:-1]))
            is_built = re.search(
                r'Successfully built ([0-9a-f]+)', data['stream'])
        elif 'error' in data:
            tqdm.write("Error {}:\n{}".format(
                data['error'], data['errorDetail']))
    if bar:
        bar.close()
    if not is_built:
        raise shub_exceptions.RemoteErrorException(
            "Build image operation failed")
    click.echo("The image {} build is completed.".format(image_name))
    # Test the image content after building it
    if not skip_tests:
        test_cmd(target, version)


def _create_or_update_progress_bar(bar, event, verbose):
    """Helper to handle build steps and track progress."""
    step_row = BUILD_STEP_REGEX.match(event['stream'])
    if step_row:
        step_id, total = [int(val) for val in step_row.groups()]
        if not bar:
            bar = _create_progress_bar(total)
        # ignore onbuild sub-steps
        if step_id > bar.pos and bar.total == total:
            bar.update()
    return bar


def _create_progress_bar(total):
    return tqdm(
        total=total,
        desc='layers',
        # XXX: click.get_text_stream or click.get_binary_stream don't
        # work well with tqdm on Windows and Python 3
        file=sys.stdout,
        # helps to update bars on resizing terminal
        dynamic_ncols=True,
        # miniters improves progress on erratic updates caused by network
        miniters=1,
        # don't need rate here, let's simplify the bar
        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}',
    )
