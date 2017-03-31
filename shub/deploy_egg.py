from __future__ import absolute_import
import os
import tempfile

import click

from shub import utils
from shub.config import get_target_conf
from shub.exceptions import (BadParameterException, NotFoundException,
                             SubcommandException)
from shub.utils import (decompress_egg_files, download_from_pypi,
                        find_executable, run_cmd)


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

SHORT_HELP = "[DEPRECATED] Build and deploy egg from source"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default='default')
@click.option("--from-url", help="Git, bazaar or mercurial repository URL")
@click.option("--git-branch", help="Git branch to checkout")
@click.option("--from-pypi", help="Name of package on pypi")
def cli(target, from_url=None, git_branch=None, from_pypi=None):
    click.secho(
        "deploy-egg was deprecated, define the eggs you would like to deploy "
        "in your scrapinghub.yml instead. See "
        "http://doc.scrapinghub.com/shub.html#deploying-dependencies",
        err=True, fg='yellow',
    )
    main(target, from_url, git_branch, from_pypi)


def main(target, from_url=None, git_branch=None, from_pypi=None):
    targetconf = get_target_conf(target)

    if from_pypi:
        _fetch_from_pypi(from_pypi)
        decompress_egg_files()
        utils.build_and_deploy_eggs(targetconf.project_id, targetconf.endpoint,
                                    targetconf.apikey)
        return

    if from_url:
        _checkout(from_url, git_branch)

    if not os.path.isfile('setup.py'):
        error = "No setup.py -- are you running from a valid Python project?"
        raise NotFoundException(error)

    utils.build_and_deploy_egg(targetconf.project_id, targetconf.endpoint,
                               targetconf.apikey)


def _checkout(repo, git_branch=None, target_dir='egg-tmp-clone'):
    tmpdir = tempfile.mkdtemp(prefix='shub-deploy-egg-from-url')

    click.echo("Cloning the repository to a tmp folder...")
    os.chdir(tmpdir)

    vcs_commands = [
        ['git', 'clone', repo, target_dir],
        ['hg', 'clone', repo, target_dir],
        ['bzr', 'branch', repo, target_dir],
    ]
    missing_exes = []
    for cmd in vcs_commands:
        exe = find_executable(cmd[0])
        if not exe:
            missing_exes.append(cmd[0])
            continue
        try:
            run_cmd([exe] + cmd[1:])
        except SubcommandException:
            pass
        else:
            break
    else:
        if missing_exes:
            click.secho(
                "shub was unable to find the following VCS executables and "
                "could not try to check out your repository with these: %s"
                "" % ', '.join(missing_exes), fg='yellow')
        raise BadParameterException(
            "\nERROR: The provided repository URL is not valid: %s\n")

    os.chdir(target_dir)

    if git_branch:
        try:
            run_cmd([find_executable('git'), 'checkout', git_branch])
        except SubcommandException:
            raise BadParameterException("Branch %s is not valid" % git_branch)
        click.echo("%s branch was checked out" % git_branch)


def _fetch_from_pypi(pkg):
    tmpdir = tempfile.mkdtemp(prefix='shub-deploy-egg-from-pypi')
    click.echo('Fetching %s from pypi' % pkg)
    download_from_pypi(tmpdir, pkg=pkg)
    click.echo('Package fetched successfully')
    os.chdir(tmpdir)
