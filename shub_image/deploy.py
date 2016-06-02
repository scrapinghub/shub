import os
import re
import ast
import json
import time
import click
import requests
import textwrap
import subprocess
from urlparse import urljoin
from retrying import retry

from shub.deploy import list_targets
from shub_image import utils
from shub_image.list import list_cmd


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

HELP = """
A command to deploy your release image to Scrapy Cloud.
Does a simple POST request to Dash API with given parameters
(some params are extracted from the project repo, i.e. spiders/scripts).
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
@click.option("--async", is_flag=True, help="enable asynchronous mode")
def cli(target, debug, version, username, password, email, async):
    deploy_cmd(target, debug, version, username, password, email, async)


def deploy_cmd(target, debug, version, username, password, email, async):
    config = utils.load_release_config()
    project, endpoint, apikey = config.get_target(target)
    image = config.get_image(target)
    version = version or config.get_version()
    image_name = utils.format_image_name(image, version)

    params = _prepare_deploy_params(
        project, version, image_name, endpoint, apikey,
        username, password, email, debug)

    if debug:
        click.echo('Deploy with params: {}'.format(params))
    req = requests.post(
        urljoin(endpoint, '/api/releases/deploy.json'),
        data=params,
        auth=(apikey, ''),
        timeout=300,
        allow_redirects=False
    )
    req.raise_for_status()
    click.echo("Deploy task results: {}".format(req))
    status_url = req.headers['location']

    status_id = utils.store_status_url(
        status_url, limit=STORE_N_LAST_STATUS_URLS)
    click.echo(
        "You can check deploy results later with "
        "'shub-image check --id {}'.".format(status_id))

    click.echo("Deploy results:")
    actual_state = _check_status_url(status_url)
    click.echo(" {}".format(actual_state))

    if not async:
        status = actual_state['status']
        while status in SYNC_DEPLOY_WAIT_STATUSES:
            time.sleep(SYNC_DEPLOY_REFRESH_TIMEOUT)
            actual_state = _check_status_url(status_url)
            if actual_state['status'] != status:
                click.echo(" {}".format(actual_state))
                status = actual_state['status']


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
                           username, password, email, debug):
    spiders = list_cmd(image_name, project, endpoint, apikey, debug)
    scripts = _extract_scripts_from_project()
    params = {'project': project,
              'version': version,
              'image_url': image_name}
    if spiders:
        params['spiders'] = spiders
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
