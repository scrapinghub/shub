import click

from shub import exceptions as shub_exceptions
from shub.config import load_shub_config, list_targets_callback
from shub.image import utils

SHORT_HELP = "Test a built image with Scrapy Cloud contract"
HELP = """
A command to test an image after build step to make sure it fits contract.

It consists of the following steps:

1) check that image exists on local machine
2) check that image has start-crawl entrypoint
3) check that image has shub-image-info entrypoint

If any of the checks fails - the test command fails as a whole. By default,
the test command is also executed automatically as a part of build command
in its end (if you do not provide -S/--skip-tests parameter explicitly).
"""

CONTRACT_CMD_NOT_FOUND_WARNING = (
    'Command %s is not found in the image. '
    'Please make sure you provided it according to Scrapy Cloud contract '
    '(https://shub.readthedocs.io/en/stable/custom-images-contract.html) or '
    'added scrapinghub-entrypoint-scrapy>=0.8.0 to your requirements file '
    'if you use Scrapy.'
)
LIST_SPIDERS_DEPRECATED_WARNING = (
    'list-spiders command is deprecated in favour of shub-image-info command: '
    'its format is described well in Scrapy Cloud contract '
    '(https://shub.readthedocs.io/en/stable/custom-images-contract.html), '
    'please review and update your code.'
)


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
@click.option("-l", "--list-targets", is_flag=True, is_eager=True,
              expose_value=False, callback=list_targets_callback,
              help="List available project names defined in your config")
@click.option("-d", "--debug", help="debug mode", is_flag=True,
              callback=utils.deprecate_debug_parameter)
@click.option("-v", "--verbose", is_flag=True,
              help="stream test logs to console")
@click.option("-V", "--version", help="release version")
def cli(target, debug, verbose, version):
    test_cmd(target, version)


def test_cmd(target, version):
    config = load_shub_config()
    image = config.get_image(target)
    version = version or config.get_version()
    image_name = utils.format_image_name(image, version)
    docker_client = utils.get_docker_client()
    for check in [_check_image_exists,
                  _check_start_crawl_entry,
                  _check_shub_image_info_entry]:
        check(image_name, docker_client)


def _check_image_exists(image_name, docker_client):
    """Check that the image exists on local machine."""
    # if there's no docker lib, the command will fail earlier
    # with an exception when getting a client in get_docker_client()
    from docker.errors import NotFound
    try:
        docker_client.inspect_image(image_name)
    except NotFound as exc:
        utils.debug_log("{}".format(exc))
        raise shub_exceptions.NotFoundException(
            "The image doesn't exist yet, please use build command at first.")


def _check_shub_image_info_entry(image_name, docker_client):
    """Check that the image has shub-image-info entrypoint"""
    status, logs = _run_docker_command(
        docker_client, image_name, ['which', 'shub-image-info'])
    if status != 0 or not logs:
        _check_fallback_to_list_spiders(image_name, docker_client)


def _check_fallback_to_list_spiders(image_name, docker_client):
    status, logs = _run_docker_command(
        docker_client, image_name, ['which', 'list-spiders'])
    if status != 0 or not logs:
        raise shub_exceptions.NotFoundException(
            CONTRACT_CMD_NOT_FOUND_WARNING % 'shub-image-info (& list-spiders)')
    else:
        click.echo(LIST_SPIDERS_DEPRECATED_WARNING)


def _check_start_crawl_entry(image_name, docker_client):
    """Check that the image has start-crawl entrypoint"""
    status, logs = _run_docker_command(
        docker_client, image_name, ['which', 'start-crawl'])
    if status != 0 or not logs:
        raise shub_exceptions.NotFoundException(
            CONTRACT_CMD_NOT_FOUND_WARNING % 'start-crawl')


def _run_docker_command(client, image_name, command):
    """A helper to execute an arbitrary cmd with given docker image"""
    container = client.create_container(image=image_name, command=command)
    try:
        client.start(container)
        statuscode = client.wait(container=container['Id'])
        logs = client.logs(container=container['Id'], stdout=True,
                           stderr=True if statuscode else False,
                           stream=False, timestamps=False)
        utils.debug_log("{} results:\n{}".format(command, logs))
        return statuscode, logs
    finally:
        client.remove_container(container)
