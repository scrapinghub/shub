import json

import click

from shub.config import load_shub_config
from shub.image import utils

SHORT_HELP = "Run a custom image locally for testing purposes."

HELP = """
TODO
"""


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument('spider', type=click.STRING)
@click.option('-a', '--argument',
              help='Spider argument (-a name=value)', multiple=True)
@click.option('-s', '--set', 'setting',
              help='Job-specific setting (-s name=value)', multiple=True)
@click.option('-e', '--environment', multiple=True,
              help='Job environment variable (-e VAR=VAL)')
# TODO script-cmd wonn't work with spider arguments!
@click.option('--script-cmd', type=click.STRING,
              help='Script command line args')
@click.option("-V", "--version", help="release version")
def cli(spider, argument, setting, environment, script_cmd, version):
    try:
        target, spider = spider.rsplit('/', 1)
    except ValueError:
        target = 'default'
    image = load_shub_config().get_image(target)
    image_name = utils.format_image_name(image, version)
    docker_client = utils.get_docker_client()
    env = _prepare_environment(
        spider, argument, setting, environment, script_cmd
    )
    _run_docker_command(docker_client, image_name, env)


def _prepare_environment(spider, arguments, settings, environment, script_cmd):
    args = dict(a.split('=', 1) for a in arguments) if arguments else {}
    settings = dict(a.split('=', 1) for a in settings) if settings else {}
    env = dict(s.split('=', 1) for s in environment) if environment else {}
    job_data = {'spider': spider, 'settings': settings, 'job_env': env}
    if script_cmd is None:
        job_data['spider_args'] = args
    else:
        job_data['job_cmd'] = [spider] + script_cmd.split()
    return {'SHUB_JOB_DATA': json.dumps(job_data)}


def _run_docker_command(client, image_name, environment):
    """A helper to execute an arbitrary cmd with given docker image"""
    container = client.create_container(
        image=image_name,
        command='test-crawl',
        environment=environment,
    )
    try:
        client.start(container)
        for log in client.logs(
                container=container['Id'], stdout=True, stderr=True,
                stream=True, timestamps=True):
            click.echo(log, nl=False)
    finally:
        client.wait(container)
        client.remove_container(container)
