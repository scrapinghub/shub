import os
import glob
import tempfile

from os.path import isdir
from subprocess import Popen, PIPE

import click

from shub.utils import find_api_key
from shub.click_utils import log, fail
from shub.utils import (make_deploy_request, pwd_hg_version, pwd_git_version,
                        pwd_bzr_version, run)


@click.command(help="Build and deploy egg from source")
@click.argument("project_id", required=True)
@click.option("--from-url", help="Git, bazaar or mercurial repository URL")
@click.option("--git-branch", help="Git branch to checkout")
def cli(project_id, from_url=None, git_branch=None):
    main(project_id, from_url, git_branch)

def main(project_id, from_url=None, git_branch=None):
    if from_url:
        _checkout(from_url, git_branch)

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


def _checkout(repo, git_branch=None):
    tmpdir = tempfile.mkdtemp(prefix='shub-deploy-egg-from-url')

    log("Cloning the repository to a tmp folder...")
    os.chdir(tmpdir)

    if (_run('git clone %s egg-tmp-clone' % repo) != 0 and
        _run('hg clone %s egg-tmp-clone' % repo) != 0 and
        _run('bzr branch %s egg-tmp-clone' % repo) != 0):
        error = "\nERROR: The provided repository URL is not valid: %s\n" % repo
        fail(error)

    os.chdir('egg-tmp-clone')

    if git_branch:
        if _run('git checkout %s' % git_branch) != 0:
            fail("Branch %s is not valid" % git_branch)
        log("%s branch was checked out" % git_branch)

def _run(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    p.communicate()
    return p.returncode
