from collections import OrderedDict

import click

from shub import exceptions as shub_exceptions
from shub.config import load_shub_config, list_targets_callback
from shub.image import utils
from shub.image.test import test_cmd

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
@click.option("-l", "--list-targets", is_flag=True, is_eager=True,
              expose_value=False, callback=list_targets_callback,
              help="List available project names defined in your config")
@click.option("-d", "--debug", help="debug mode", is_flag=True,
              callback=utils.deprecate_debug_parameter)
@click.option("-v", "--verbose", is_flag=True,
              help="stream push logs to console")
@click.option("-V", "--version", help="release version")
@click.option("--username", help="docker registry name")
@click.option("--password", help="docker registry password")
@click.option("--email", help="docker registry email")
@click.option("--apikey", help="SH apikey to use built-in registry")
@click.option("--insecure", is_flag=True, help="use insecure registry")
@click.option("-S", "--skip-tests", help="skip testing image", is_flag=True)
def cli(target, debug, verbose, version, username, password, email, apikey,
        insecure, skip_tests):
    push_cmd(target, version, username, password, email, apikey, insecure, skip_tests)


def push_cmd(target, version, username, password, email, apikey, insecure, skip_tests):
    # Test the image content after building it
    if not skip_tests:
        test_cmd(target, version)

    client = utils.get_docker_client()
    config = load_shub_config()
    image = config.get_image(target)
    username, password = utils.get_credentials(
        username=username, password=password, insecure=insecure,
        apikey=apikey, target_apikey=config.get_apikey(target))

    if username:
        _execute_push_login(client, image, username, password, email)
    image_name = utils.format_image_name(image, version)
    click.echo("Pushing {} to the registry.".format(image_name))
    events = client.push(image_name, stream=True, decode=True,
                         insecure_registry=not bool(username))
    if utils.is_verbose():
        push_progress_cls = _LoggedPushProgress
    else:
        push_progress_cls = _PushProgress
    push_progress = push_progress_cls(events)
    push_progress.show()
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


class _LoggedPushProgress(utils.BaseProgress):
    """Visualize push progress in verbose mode.

    Output all the events received from the docker daemon.
    """
    def handle_event(self, event):
        super(_LoggedPushProgress, self).handle_event(event)
        if 'status' in event:
            self.handle_status_event(event)

    def handle_status_event(self, event):
        msg = "Logs:{} {}".format(event['status'], event.get('progress'))
        utils.debug_log(msg)


class _PushProgress(_LoggedPushProgress):
    """Visualize push progress in non-verbose mode.

    Show total progress bar and separate bar for each pushed layer.
    """

    def __init__(self, push_events):
        super(_PushProgress, self).__init__(push_events)
        # Total bar repesents total progress in terms of amount of layers.
        self.total_bar = self._create_total_bar()
        self.layers = set()
        # XXX: has to be OrderedDict to make tqdm.write/click.echo work as expected.
        # Otherwise it writes at random position, usually in the middle of the progress bars.
        self.layers_bars = OrderedDict()

    def handle_status_event(self, event):
        layer_id = event.get('id')
        status = event.get('status')
        progress = event.get('progressDetail')
        # `preparing` events are correlated with amount of layers to push
        if status in ('Preparing', 'Waiting'):
            self._add_layer(layer_id)
        # the events are final and used to update total bar once per layer
        elif status in ('Layer already exists', 'Pushed'):
            self._add_layer(layer_id)
            self.total_bar.update()
        # `pushing` events represents actual push process per layer
        elif event.get('status') == 'Pushing' and progress:
            progress_current = progress.get('current', 0)
            progress_total = max(progress.get('total', 0), progress_current)
            if layer_id not in self.layers_bars:
                if not progress_total:
                    return
                # create a progress bar per pushed layer
                self.layers_bars[layer_id] = self._create_bar_per_layer(
                    layer_id, progress_total, progress_current)
            bar = self.layers_bars[layer_id]
            bar.total = max(bar.total, progress_total)
            bar.update(max(progress_current - bar.n, 0))

    def _add_layer(self, layer_id):
        self.layers.add(layer_id)
        self.total_bar.total = max(self.total_bar.total, len(self.layers))
        self.total_bar.refresh()

    def show(self):
        super(_PushProgress, self).show()
        self.total_bar.close()
        for bar in self.layers_bars.values():
            bar.close()

    def _create_total_bar(self):
        return utils.create_progress_bar(
            total=1,
            desc='Layers',
            # don't need rate here, let's simplify the bar
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}'
        )

    def _create_bar_per_layer(self, layer_id, total, initial):
        return utils.create_progress_bar(
            desc=layer_id,
            total=total,
            initial=initial,
            unit='B',
            unit_scale=True,
            # don't need estimates here, keep only rate
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{rate_fmt}]',
        )
