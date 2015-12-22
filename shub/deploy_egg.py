import os
import tempfile

from subprocess import Popen, PIPE

import click

from click import ClickException

from shub.config import get_target
from shub import utils
from shub.utils import run, decompress_egg_files


@click.command(help="Build and deploy egg from source")
@click.argument("target", required=False, default='default')
@click.option("--from-url", help="Git, bazaar or mercurial repository URL")
@click.option("--git-branch", help="Git branch to checkout")
@click.option("--from-pypi", help="Name of package on pypi")
def cli(target, from_url=None, git_branch=None, from_pypi=None):
    main(target, from_url, git_branch, from_pypi)


def main(target, from_url=None, git_branch=None, from_pypi=None):
    project, endpoint, apikey = get_target(target)

    if from_pypi:
        _fetch_from_pypi(from_pypi)
        decompress_egg_files()
        utils.build_and_deploy_eggs(project, endpoint, apikey)
        return

    if from_url:
        _checkout(from_url, git_branch)

    if not os.path.isfile('setup.py'):
        error = "No setup.py -- are you running from a valid Python project?"
        raise ClickException(error)

    utils.build_and_deploy_egg(project, endpoint, apikey)


def _checkout(repo, git_branch=None):
    tmpdir = tempfile.mkdtemp(prefix='shub-deploy-egg-from-url')

    click.echo("Cloning the repository to a tmp folder...")
    os.chdir(tmpdir)

    if (_run('git clone %s egg-tmp-clone' % repo) != 0 and
            _run('hg clone %s egg-tmp-clone' % repo) != 0 and
            _run('bzr branch %s egg-tmp-clone' % repo) != 0):
        error = "\nERROR: The provided repository URL is not valid: %s\n"
        raise ClickException(error % repo)

    os.chdir('egg-tmp-clone')

    if git_branch:
        if _run('git checkout %s' % git_branch) != 0:
            raise ClickException("Branch %s is not valid" % git_branch)
        click.echo("%s branch was checked out" % git_branch)


def _fetch_from_pypi(pkg):
    tmpdir = tempfile.mkdtemp(prefix='shub-deploy-egg-from-pypi')

    click.echo('Fetching %s from pypi' % pkg)
    pip_cmd = "pip install -d %s %s --no-deps --no-use-wheel" % (tmpdir, pkg)
    click.echo(run(pip_cmd))
    click.echo('Package fetched successfully')
    os.chdir(tmpdir)


def _run(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    p.communicate()
    return p.returncode
