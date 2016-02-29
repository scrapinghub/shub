import os
import re
import ast
import json
import click
import requests
import textwrap
import subprocess
from urlparse import urljoin

from shub.deploy import list_targets
from kumo_release import utils


VALIDSPIDERNAME = re.compile('^[a-z0-9][-._a-z0-9]+$', re.I)
STORE_N_LAST_STATUS_URLS = 5
SHORT_HELP = 'Deploy a release image to Scrapy cloud'

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
@click.option("--sync", is_flag=True, help="enable synchronous mode")
def cli(target, debug, version, username, password, email, sync):
    deploy_cmd(target, debug, version, username, password, email, sync)


def deploy_cmd(target, debug, version, username, password, email, sync):
    config = utils.load_release_config()
    project, endpoint, apikey = config.get_target(target)
    image = config.get_image(target)
    version = version or config.get_version()
    image_name = utils.format_image_name(image, version)

    params = _prepare_deploy_params(
        project, version, image_name,
        username, password, email, sync)
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
        "'kumo-release check --id {}'.".format(status_id))

    status_req = requests.get(status_url, timeout=300)
    status_req.raise_for_status()
    result = status_req.json()
    click.echo("Deploy results: {}".format(result))


def _prepare_deploy_params(project, version, image_name,
                           username, password, email, sync):
    spiders = _extract_spiders_from_project()
    scripts = _extract_scripts_from_project()
    params = {'project': project,
              'version': version,
              'image_url': image_name,
              'spiders': spiders}
    if scripts:
        params['scripts'] = scripts
    if sync:
        params['sync'] = True
    if not username:
        params['pull_insecure_registry'] = True
    else:
        params['pull_auth_config'] = json.dumps(
            {'username': username,
             'password': password,
             'email': email}, sort_keys=True)
    return params


def _extract_spiders_from_project():
    spiders = []
    try:
        raw_output = subprocess.check_output(["scrapy", "list"])
        spiders = sorted(filter(
            VALIDSPIDERNAME.match, raw_output.splitlines()))
    except subprocess.CalledProcessError as exc:
        click.echo(
            "Can't extract spiders from project:\n{}".format(exc.output))
    return ','.join(spiders)


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
