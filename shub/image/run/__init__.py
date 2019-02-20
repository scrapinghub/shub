import json
import stat
import shlex
import signal
import os.path
from os import stat as os_stat
from shutil import copyfile

import click

from shub.config import load_shub_config
from shub.image import utils


SHORT_HELP = 'Run custom image locally.'
HELP = """
Run a custom Docker image locally.

The command should be helpful to ensure that your custom image is properly
written and do some preliminary local tests before pushing it to Scrapy Cloud.

Most of the command parameters coincide with parameters for 'shub schedule'
command to simplfy its usage.

The `spider` argument should match the spider's name, e.g.:

    shub image run myspider

A more advanced example of using non-default target with settings/arguments:

    shub image run production/myspider -a ARG1=VAL1 -s LOG_LEVEL=DEBUG
"""

SCRAPINGHUB_VOLUME = '/scrapinghub'
WRAPPER_FILENAME = 'start-crawl-local'
WRAPPER_LOCAL_PATH = os.path.join(os.path.dirname(__file__), 'wrapper.py')
WRAPPER_IMAGE_PATH = os.path.join(SCRAPINGHUB_VOLUME, WRAPPER_FILENAME)


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("spider", type=click.STRING)
@click.option('-a', '--argument', 'args',
              help='Spider argument (-a name=value)', multiple=True)
@click.option('-s', '--set', 'settings',
              help='Job-specific setting (-s name=value)', multiple=True)
@click.option('-e', '--environment', multiple=True,
              help='Job environment variable (-e VAR=VAL)')
@click.option("-V", "--version", help="use custom release version")
@click.option("-v", "--verbose", is_flag=True,
              help="stream additional logs to console")
@click.option("-k", "--keep-volume", help="Keep volume folder", is_flag=True)
def cli(spider, args, settings, environment, version, verbose, keep_volume):
    run_cmd(spider, args, settings, environment, version, keep_volume)


def run_cmd(spider, args, settings, environment, version, keep_volume):
    try:
        target, spider = spider.rsplit('/', 1)
    except ValueError:
        target = 'default'

    config = load_shub_config()
    image = config.get_image(target)
    version = version or config.get_version()
    image_name = utils.format_image_name(image, version)
    docker_client = utils.get_docker_client()

    env = _format_environment(spider, args, settings, environment)
    _run_with_docker(docker_client, image_name, env, keep_volume)


def _format_environment(spider, args, settings, environment):
    """Convert all input crawl args to environment variables."""
    # required defaults, can be overwritten with meta if needed
    job_data = {'spider': spider, 'key': '1/2/3', 'auth': '<auth>'}

    args = dict(x.split('=', 1) for x in args)
    cmd_args = shlex.split(args.pop('cmd_args', ''))
    if spider.startswith('py:'):
        job_data['job_cmd'] = [spider] + cmd_args
    else:
        job_data['spider_args'] = args
    meta = args.pop('meta', None)
    if meta:
        job_data.update(json.loads(meta))

    job_environment = dict(x.split('=', 1) for x in environment)
    job_settings = dict(x.split('=', 1) for x in settings)
    return {
        'SHUB_JOBKEY': job_data['key'],
        'SHUB_SPIDER': spider,
        'SHUB_JOB_DATA': _json_dumps(job_data),
        'SHUB_JOB_ENV': _json_dumps(job_environment),
        'SHUB_SETTINGS': _json_dumps({'job_settings': job_settings}),
        'PYTHONUNBUFFERED': 1,
    }


def _json_dumps(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'))


def _run_with_docker(client, image_name, env, keep_volume=False):
    """Run a local docker container with the given custom image."""

    def _signal_handler(sig, _):
        client.kill(container, sig)

    tmpdir_kw = {'prefix': 'shub-image-run-', 'cleanup': not keep_volume}
    with utils.make_temp_directory(**tmpdir_kw) as volume_dir:
        container = _create_container(client, image_name, env, volume_dir)
        try:
            client.start(container)
            signal.signal(signal.SIGINT, _signal_handler)
            signal.signal(signal.SIGTERM, _signal_handler)
            for log in client.logs(container, stream=True):
                click.echo(log.rstrip())
        finally:
            client.remove_container(container, force=True)


def _create_container(client, image_name, environment, volume_dir):
    """Create a docker container and customize its setup."""
    # copy start-crawl wrapper to the volume temporary directory
    wrapper_cont_path = os.path.join(volume_dir, WRAPPER_FILENAME)
    copyfile(WRAPPER_LOCAL_PATH, wrapper_cont_path)
    wrapper_perms = os_stat(wrapper_cont_path).st_mode | stat.S_IEXEC
    os.chmod(wrapper_cont_path, wrapper_perms)  # must be executable
    fifo_path = os.path.join(volume_dir, 'scrapinghub.fifo')
    environment['SHUB_FIFO_PATH'] = fifo_path
    # keep using default /scrapinghub volume but mount it as a temporary
    # directory in the host /tmp/ to have access to the files in needed
    binds = {volume_dir: {'bind': SCRAPINGHUB_VOLUME, 'mode': 'rw'}}
    host_config = client.create_host_config(binds=binds)
    return client.create_container(
        image=image_name,
        command=[WRAPPER_IMAGE_PATH],
        environment=environment,
        volumes=[volume_dir],
        host_config=host_config,
    )
