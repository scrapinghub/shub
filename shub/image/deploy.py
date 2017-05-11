import os
import re
import ast
import json
import time
import textwrap

import click
import requests
from retrying import retry
from six.moves.urllib.parse import urljoin

from shub.config import load_shub_config, list_targets_callback
from shub.exceptions import ShubException
from shub.image import utils
from shub.image import list as list_mod


VALIDSPIDERNAME = re.compile('^[a-z0-9][-._a-z0-9]+$', re.I)
STORE_N_LAST_STATUS_URLS = 5
SYNC_DEPLOY_REFRESH_TIMEOUT = 1
SYNC_DEPLOY_WAIT_STATUSES = ['pending', 'started', 'retry', 'progress']
SHORT_HELP = 'Deploy a release image to Scrapy cloud'
CHECK_RETRY_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.HTTPError,
)
# Exponential retry timeouts: min(2^n * multiplier, max)
# [2s, 4s, 8s, 16s, 30s] = 60s
CHECK_RETRY_ATTEMPTS = 6
CHECK_RETRY_EXP_MULTIPLIER = 1000
CHECK_RETRY_EXP_MAX = 30000
DEFAULT_TOTAL_PROGRESS = 100

HELP = """
A command to deploy your release image to Scrapy Cloud.
Does a simple POST request to Dash API with given parameters
(some params are extracted from the project repo, i.e. spiders/scripts).
"""


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
@click.option("-l", "--list-targets", is_flag=True, is_eager=True,
              expose_value=False, callback=list_targets_callback,
              help="List available project names defined in your config")
@click.option("-d", "--debug", help="debug mode", is_flag=True,
              callback=utils.deprecate_debug_parameter)
@click.option("-v", "--verbose", is_flag=True,
              help="stream deploy logs to console")
@click.option("-V", "--version", help="release version")
@click.option("--username", help="docker registry name")
@click.option("--password", help="docker registry password")
@click.option("--email", help="docker registry email")
@click.option("--apikey", help="SH apikey to use built-in registry")
@click.option("--insecure", is_flag=True, help="use insecure registry")
@click.option("--async", is_flag=True, help="[DEPRECATED] enable asynchronous mode",
              callback=utils.deprecate_async_parameter)
def cli(target, debug, verbose, version, username, password, email,
        apikey, insecure, async):
    deploy_cmd(target, version, username, password, email,
               apikey, insecure, async)


def deploy_cmd(target, version, username, password, email,
               apikey, insecure, async):
    config = load_shub_config()
    target_conf = config.get_target_conf(target)
    endpoint, target_apikey = target_conf.endpoint, target_conf.apikey
    image = config.get_image(target)
    version = version or config.get_version()
    image_name = utils.format_image_name(image, version)
    username, password = utils.get_credentials(
        username=username, password=password, insecure=insecure,
        apikey=apikey, target_apikey=target_apikey)

    apikey = apikey or target_apikey
    params = _prepare_deploy_params(
        target_conf.project_id, version, image_name, endpoint, apikey,
        username, password, email)

    click.echo("Deploying {}".format(image_name))
    utils.debug_log('Deploy parameters: {}'.format(params))
    req = requests.post(
        urljoin(endpoint, '/api/releases/deploy.json'),
        data=params,
        auth=(apikey, ''),
        timeout=300,
        allow_redirects=False
    )
    if req.status_code == 400:
        reason = req.json().get('non_field_errors')
        raise ShubException('\n'.join(reason) if reason else req.text)
    req.raise_for_status()
    status_url = req.headers['location']
    status_id = utils.store_status_url(
        status_url, limit=STORE_N_LAST_STATUS_URLS)
    click.echo(
        "You can check deploy results later with "
        "'shub image check --id {}'.".format(status_id))
    if async:
        return
    if utils.is_verbose():
        deploy_progress_cls = _LoggedDeployProgress
    else:
        deploy_progress_cls = _DeployProgress
    deploy_progress = deploy_progress_cls(status_url)
    deploy_progress.show()


class _BaseDeployProgress(object):

    def __init__(self, status_url):
        self.status_url = status_url

    def show(self):
        while True:
            event = _check_status_url(self.status_url)
            self.handle_event(event)
            if event['status'] not in SYNC_DEPLOY_WAIT_STATUSES:
                break
            time.sleep(SYNC_DEPLOY_REFRESH_TIMEOUT)

    def handle_event(self, event):
        raise NotImplemented('Must be implemented in subclasses')


class _LoggedDeployProgress(_BaseDeployProgress):
    """Visualize deploy progress in verbose mode.

    Output all the distinct events received from the service.
    """
    def __init__(self, status_url):
        super(_LoggedDeployProgress, self).__init__(status_url)
        self.previous_event = None
        click.echo("Deploy results:")

    def handle_event(self, event):
        if event != self.previous_event:
            click.echo("{}".format(event))
            self.previous_event = event


class _DeployProgress(_BaseDeployProgress):
    """Visualize deploy progress in non-verbose mode.

    Uses a progress bar to track total progress.
    """
    def __init__(self, status_url):
        super(_DeployProgress, self).__init__(status_url)
        self.progress_bar = self._create_progress_bar()
        self.result_event = None

    def show(self):
        super(_DeployProgress, self).show()
        # it's possible that release process finishes instantly without
        # providing enough information to fill progress bar completely
        if self.result_event and self.result_event['status'] == 'ok':
            delta = max(self.progress_bar.total - self.progress_bar.n, 0)
            self.progress_bar.update(delta)
        self.progress_bar.close()
        # last event with non-waiting status contains successful result or
        # error result from the service with error details
        if self.result_event:
            click.echo("Deploy results:{}".format(self.result_event))

    def handle_event(self, event):
        if 'progress' in event and 'total' in event:
            self.progress_bar.total = event['total']
            self.progress_bar.update(max(event['progress'] - self.progress_bar.n, 0))
        elif event['status'] not in SYNC_DEPLOY_WAIT_STATUSES:
            self.result_event = event

    def _create_progress_bar(self):
        return utils.create_progress_bar(
            total=DEFAULT_TOTAL_PROGRESS,
            desc='Progress',
            # don't need rate here, let's simplify the bar
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}'
        )


def _retry_on_requests_error(exception):
    return isinstance(exception, CHECK_RETRY_EXCEPTIONS)


@retry(retry_on_exception=_retry_on_requests_error,
       stop_max_attempt_number=CHECK_RETRY_ATTEMPTS,
       wait_exponential_multiplier=CHECK_RETRY_EXP_MULTIPLIER,
       wait_exponential_max=CHECK_RETRY_EXP_MAX)
def _check_status_url(status_url):
    status_req = requests.get(status_url, timeout=300)
    status_req.raise_for_status()
    return status_req.json()


def _prepare_deploy_params(project, version, image_name, endpoint, apikey,
                           username, password, email):
    # Reusing shub.image.list logic to get spiders list
    spiders = list_mod.list_cmd(image_name, project, endpoint, apikey)
    scripts = _extract_scripts_from_project()
    params = {'project': project,
              'version': version,
              'image_url': image_name}
    if spiders:
        params['spiders'] = ','.join(spiders)
    if scripts:
        params['scripts'] = scripts
    if not username:
        params['pull_insecure_registry'] = True
    else:
        params['pull_auth_config'] = json.dumps(
            {'username': username,
             'password': password,
             'email': email}, sort_keys=True)
    return params


def _extract_scripts_from_project(setup_filename='setup.py'):
    """Parse setup.py and return scripts"""
    if not os.path.isfile(setup_filename):
        return ''
    mock_setup = textwrap.dedent('''\
    def setup(*args, **kwargs):
        __setup_calls__.append((args, kwargs))
    ''')
    parsed_mock_setup = ast.parse(mock_setup, filename=setup_filename)
    with open(setup_filename, 'rt') as setup_file:
        parsed = ast.parse(setup_file.read())
        for index, node in enumerate(parsed.body[:]):
            if (not isinstance(node, ast.Expr) or
                    not isinstance(node.value, ast.Call) or
                    node.value.func.id != 'setup'):
                continue
            parsed.body[index:index] = parsed_mock_setup.body
            break
    fixed = ast.fix_missing_locations(parsed)
    codeobj = compile(fixed, setup_filename, 'exec')
    local_vars = {}
    global_vars = {'__setup_calls__': []}
    exec(codeobj, global_vars, local_vars)
    _, kwargs = global_vars['__setup_calls__'][0]
    return ','.join([os.path.basename(f) for f in kwargs.get('scripts', [])])
