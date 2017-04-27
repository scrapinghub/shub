import os
import re

import click

from shub import exceptions as shub_exceptions
from shub.config import load_shub_config, list_targets_callback
from shub.image import utils
from shub.image.test import test_cmd
from shub.utils import create_scrapinghub_yml_wizard


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

BUILD_STEP_REGEX = re.compile(r'Step (\d+)/(\d+) :.*')
BUILD_SUCCESS_REGEX = re.compile(r'Successfully built ([0-9a-f]+)')


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
@click.option("-l", "--list-targets", is_flag=True, is_eager=True,
              expose_value=False, callback=list_targets_callback,
              help="List available project names defined in your config")
@click.option("-d", "--debug", help="debug mode", is_flag=True,
              callback=utils.deprecate_debug_parameter)
@click.option("-v", "--verbose", is_flag=True,
              help="stream build logs to console")
@click.option("-V", "--version", help="release version")
@click.option("-S", "--skip-tests", help="skip testing image", is_flag=True)
def cli(target, debug, verbose, version, skip_tests):
    build_cmd(target, version, skip_tests)


def build_cmd(target, version, skip_tests):
    config = load_shub_config()
    image_configured = (
        target in config.projects and config.get_target_conf(target).image)
    if not target.isdigit() and not image_configured:
        create_scrapinghub_yml_wizard(config, target=target, image=True)
    client = utils.get_docker_client()
    project_dir = utils.get_project_dir()
    image = config.get_image(target)
    image_name = utils.format_image_name(image, version)
    if not os.path.exists(os.path.join(project_dir, 'Dockerfile')):
        raise shub_exceptions.NotFoundException(
            "Dockerfile is not found and it is required because project '{}' is configured "
            "to deploy Docker images. Please add a Dockerfile that will be used to build "
            "the image and retry this command. If you want to migrate an existing Scrapy project "
            "you can use `shub image init` command to create a Dockerfile.".format(target))
    if utils.is_verbose():
        build_progress_cls = _LoggedBuildProgress
    else:
        build_progress_cls = _BuildProgress
    click.echo("Building {}.".format(image_name))
    events = client.build(path=project_dir, tag=image_name, decode=True)
    build_progress = build_progress_cls(events)
    build_progress.show()
    click.echo("The image {} build is completed.".format(image_name))
    # Test the image content after building it
    if not skip_tests:
        test_cmd(target, version)


class _LoggedBuildProgress(utils.BaseProgress):
    """Visualize build progress in verbose mode.

    Output all the events received from the docker daemon.
    """
    def handle_event(self, event):
        super(_LoggedBuildProgress, self).handle_event(event)
        if 'stream' in event:
            self.handle_stream_event(event)

    def handle_stream_event(self, event):
        utils.debug_log("{}".format(event['stream'][:-1]))


class _BuildProgress(_LoggedBuildProgress):
    """Visualize build progress in non-verbose mode.

    Show total progress bar.
    """

    def __init__(self, events):
        super(_BuildProgress, self).__init__(events)
        self.bar = utils.create_progress_bar(
            total=1,
            desc='Steps',
            # don't need rate here, let's simplify the bar
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}',
        )
        self.is_built = False

    def show(self):
        super(_BuildProgress, self).show()
        if self.bar:
            self.bar.close()
        if not self.is_built:
            raise shub_exceptions.RemoteErrorException(
                "Build image operation failed")

    def handle_stream_event(self, event):
        if BUILD_SUCCESS_REGEX.search(event['stream']):
            self.is_built = True
            return
        step_row = BUILD_STEP_REGEX.match(event['stream'])
        if not step_row:
            return
        step_id, total = [int(val) for val in step_row.groups()]
        self.bar.total = max(self.bar.total, total)
        # ignore onbuild sub-steps
        if step_id > self.bar.n and self.bar.total == total:
            self.bar.update()
