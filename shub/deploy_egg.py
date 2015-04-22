import os
import glob
import subprocess

from os.path import isdir

import click

from shub.utils import find_api_key
from shub.click_utils import log, fail
from shub.utils import (make_deploy_request, pwd_hg_version, pwd_git_version,
                        pwd_bzr_version)


@click.command(help="Build and deploy egg from source")
@click.argument("project_id", required=True)
def cli(project_id):
    if not os.path.isfile('setup.py'):
        error = "No setup.py -- are you running from a valid Python project?"
        fail(error)

    run('python setup.py bdist_egg')
    _deploy_dependency_egg(find_api_key(), project_id)

def _deploy_dependency_egg(shub_apikey, project_id):
    name = _get_dependency_name()
    version = _get_dependency_version(name)
    egg_name, egg_path = _get_egg_info(name)

    url = 'https://dash.scrapinghub.com/api/eggs/add.json'
    data = {'project': project_id, 'name': name, 'version': version}
    files = {'egg': (egg_name, open(egg_path, 'rb'))}
    auth = (shub_apikey, '')

    log('Deploying dependency to Scrapy Cloud project "%s"' % project_id)
    make_deploy_request(url, data, files, auth)
    success = "Deployed eggs list at: https://dash.scrapinghub.com/p/%s/eggs"
    log(success % project_id)


def _get_dependency_name():
    return run('python setup.py --name')


def _get_dependency_version(name):
    if isdir('.git'):
        return pwd_git_version()
    elif isdir('.hg'):
        return pwd_hg_version()
    elif isdir('.bzr'):
        return pwd_bzr_version()

    return "%s-%s" % (name, run('python setup.py --version'))


def _get_egg_info(name):
    egg_filename = name.replace('-', '_')
    egg_path_glob = os.path.join('dist', '%s*' % egg_filename)
    egg_path = glob.glob(egg_path_glob)[0]
    return (egg_filename, egg_path)


def run(cmd):
    output = subprocess.check_output(cmd, shell=True)
    return output.strip()
