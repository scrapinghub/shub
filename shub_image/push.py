import json
import click

from shub.deploy import list_targets
from shub import exceptions as shub_exceptions
from shub_image import utils

SHORT_HELP = 'Push an image to a specified docker registry'

HELP = """
A command to push your image to specified docker registry.

The command is a simple wrapper for `docker push` command and uses docker
daemon on your system to build an image. The only differences are that it
can generate correct image version and provide easy registry login logic.

The optional params are mostly related with registry authorization.
By default, the tool tries to call the registry in insecure manner,
otherwise you have to enter your credentials (at least username/password).
"""


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
@click.option("-l", "--list-targets", help="list available targets",
              is_flag=True, is_eager=True, expose_value=False,
              callback=list_targets)
@click.option("-d", "--debug", help="debug mode", is_flag=True)
@click.option("--version", help="release version")
@click.option("--username", help="docker registry name")
@click.option("--password", help="docker registry password")
@click.option("--email", help="docker registry email")
def cli(target, debug, version, username, password, email):
    push_cmd(target, debug, version, username, password, email)


def push_cmd(target, debug, version, username, password, email):
    client = utils.get_docker_client()
    config = utils.load_release_config()
    image = config.get_image(target)
    if username:
        _execute_push_login(client, image, username, password, email)
    image_name = utils.format_image_name(image, version)
    click.echo("Pushing {} to the registry.".format(image_name))
    for line in client.push(image_name, stream=True,
                            insecure_registry=not bool(username)):
        data = json.loads(line)
        if 'status' in data and debug:
            click.echo("Logs:{} {}".format(data['status'],
                                           data.get('progress')))
        if 'error' in data:
            click.echo("Error {}: {}".format(data['error'],
                                             data['errorDetail']))
            raise shub_exceptions.RemoteErrorException(
                "Docker push operation failed")
    click.echo("The image {} pushed successfully.".format(image_name))


def _execute_push_login(client, image, username, password, email):
    """Login if there're provided credentials for the registry"""
    components = image.split('/')
    registry = components[0] if len(components) == 3 else None
    resp = client.login(username=username, password=password,
                        email=email, registry=registry, reauth=False)
    if not (isinstance(resp, dict) and 'username' in resp or
            ('Status' in resp and resp['Status'] == 'Login Succeeded')):
        raise shub_exceptions.RemoteErrorException(
            "Docker registry login error.")
    click.echo("Login to {} succeeded.".format(registry))
