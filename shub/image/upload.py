import click

from shub.deploy import list_targets
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
@click.option("-l", "--list-targets", help="list available targets",
              is_flag=True, is_eager=True, expose_value=False,
              callback=list_targets)
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
@click.option("--async", is_flag=True, help="enable asynchronous mode")
@click.option("-S", "--skip-tests", help="skip testing image", is_flag=True)
def cli(target, debug, verbose, version, username, password, email,
        apikey, insecure, async, skip_tests):
    build.build_cmd(target, version, skip_tests)
    push.push_cmd(target, version, username, password, email, apikey, insecure)
    deploy.deploy_cmd(target, version, username, password, email,
                      apikey, insecure, async)
