import click

from shub.config import list_targets_callback
from shub.image import build
from shub.image import push
from shub.image import deploy
from shub.image import utils


SHORT_HELP = "Shortcut command for build-push-deploy chain"
HELP = """
Upload command is a handy shortcut to rebuild and redeploy your project
(in other words it does consecutive calls of build-push-deploy cmds).

Obviously it accepts all the options for the commands above.
"""


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
@click.option("-l", "--list-targets", is_flag=True, is_eager=True,
              expose_value=False, callback=list_targets_callback,
              help="List available project names defined in your config")
@click.option("-d", "--debug", help="debug mode", is_flag=True,
              callback=utils.deprecate_debug_parameter)
@click.option("-v", "--verbose", is_flag=True,
              help="stream upload logs to console")
@click.option("-V", "--version", help="release version")
@click.option("--username", help="docker registry name")
@click.option("--password", help="docker registry password")
@click.option("--email", help="docker registry email")
@click.option("--apikey", help="SH apikey to use built-in registry")
@click.option("--insecure", is_flag=True, help="use insecure registry")
@click.option("--async", is_flag=True, help="[DEPRECATED] enable asynchronous mode",
              callback=utils.deprecate_async_parameter)
@click.option("-S", "--skip-tests", help="skip testing image", is_flag=True)
@click.option("-f", "--file", "filename", default='Dockerfile',
              help="Name of the Dockerfile (Default is 'PATH/Dockerfile')")
def cli(target, debug, verbose, version, username, password, email,
        apikey, insecure, async, skip_tests, filename):
    upload_cmd(target, version, username, password, email, apikey, insecure,
               async, skip_tests, filename)


def upload_cmd(target, version, username=None, password=None, email=None,
               apikey=None, insecure=False, async=False, skip_tests=False,
               filename='Dockerfile'):
    build.build_cmd(target, version, skip_tests, filename=filename)
    # skip tests for push command anyway because they run in build command if not skipped
    push.push_cmd(target, version, username, password, email, apikey,
                  insecure, skip_tests=True)
    deploy.deploy_cmd(target, version, username, password, email,
                      apikey, insecure, async)
