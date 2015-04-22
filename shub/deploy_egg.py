import os
import glob
import subprocess

from os.path import isdir

import click

from shub.utils import find_api_key
from shub.click_utils import log, fail
from shub.utils import make_deploy_request


@click.command(help="Build and deploy egg from source")
@click.argument("project_id", required=True)
def cli(project_id):
    if not os.path.isfile('setup.py'):
        error = "No setup.py -- are you running from a valid Python project?"
        fail(error)

    run('python setup.py bdist_egg')
    _deploy_egg(find_api_key(), project_id)

def _deploy_egg(shub_apikey, project_id):
    name = _get_project_name()
    version = _get_project_version(name)
    egg_name, egg_path = _get_egg_info(name)

    url = 'https://dash.scrapinghub.com/api/eggs/add.json'
    data = {'project': project_id, 'name': name, 'version': version}
    files = {'egg': (egg_name, open(egg_path, 'rb'))}
    auth = (shub_apikey, '')

    log('Deploying to Scrapy Cloud project "%s"' % project_id)
    make_deploy_request(url, data, files, auth)
    success = "Deployed eggs list at: https://dash.scrapinghub.com/p/%s/eggs"
    log(success % project_id)


def _get_project_name():
    return run('python setup.py --name')


def _get_project_version(name):
    if isdir('.git'):
        return run('gt rev-parse --short --verify HEAD')
    elif isdir('.hg'):
        return run('hg id -i')[:7]
    elif isdir('.bzr'):
        return run('bzr revno')

    return "%s-%s" % (name, run('python setup.py --version'))


def _get_egg_info(name):
    egg_filename = name.replace('-', '_')
    egg_path_glob = os.path.join('dist', '%s*' % egg_filename)
    egg_path = glob.glob(egg_path_glob)[0]
    return (egg_filename, egg_path)


def run(cmd):
    output = subprocess.check_output(cmd, shell=True)
    return output.strip()
