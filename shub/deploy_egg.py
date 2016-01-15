import os
import tempfile

from subprocess import Popen, PIPE

import click

from shub import utils
from shub.config import get_target
from shub.exceptions import BadParameterException, NotFoundException
from shub.utils import decompress_egg_files, find_exe, run


HELP = """
Build a Python egg from source and deploy it to Scrapy Cloud.

You can either deploy to your default target (as defined in scrapinghub.yml),
or explicitly supply a numerical project ID or a target defined in
scrapinghub.yml (see shub deploy).

By default, shub will try to build the egg using the current folder's setup.py.
You can also build the egg from a remote (git/mercurial/bazaar) repository by
using the --from-url option:

    shub deploy-egg --from-url https://github.com/scrapinghub/shub.git

For git repositories, you may additionally specify the branch to be checked
out:

    shub deploy-egg --from-url https://xy.git --git-branch my-feature

Alternatively, you can build the egg from a PyPI package:

    shub deploy-egg --from-pypi shub
"""

SHORT_HELP = "Build and deploy egg from source"


@click.command(help=HELP, short_help=SHORT_HELP)
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
        raise NotFoundException(error)

    utils.build_and_deploy_egg(project, endpoint, apikey)


def _checkout(repo, git_branch=None):
    tmpdir = tempfile.mkdtemp(prefix='shub-deploy-egg-from-url')

    click.echo("Cloning the repository to a tmp folder...")
    os.chdir(tmpdir)

    if (_run('git clone %s egg-tmp-clone' % repo) != 0 and
            _run('hg clone %s egg-tmp-clone' % repo) != 0 and
            _run('bzr branch %s egg-tmp-clone' % repo) != 0):
        error = "\nERROR: The provided repository URL is not valid: %s\n"
        raise BadParameterException(error % repo)

    os.chdir('egg-tmp-clone')

    if git_branch:
        if _run('git checkout %s' % git_branch) != 0:
            raise BadParameterException("Branch %s is not valid" % git_branch)
        click.echo("%s branch was checked out" % git_branch)


def _fetch_from_pypi(pkg):
    pip = find_exe('pip')
    tmpdir = tempfile.mkdtemp(prefix='shub-deploy-egg-from-pypi')
    click.echo('Fetching %s from pypi' % pkg)
    pip_cmd = ("%s install -d %s %s --no-deps --no-use-wheel"
               "" % (pip, tmpdir, pkg))
    click.echo(run(pip_cmd))
    click.echo('Package fetched successfully')
    os.chdir(tmpdir)


def _run(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    p.communicate()
    return p.returncode
