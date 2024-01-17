import click
import os
import tempfile
import shutil

from shub import DEPLOY_DOCS_LINK
from shub.config import get_target_conf
from shub.utils import (build_and_deploy_eggs, decompress_egg_files,
                        download_from_pypi)


HELP = """
Build eggs of your project's requirements and deploy them to Scrapy Cloud.

You can either deploy to your default target (as defined in scrapinghub.yml),
or explicitly supply a numerical project ID or a target defined in
scrapinghub.yml (see shub deploy).

By default, requirements will be read from requirements.txt. You may supply a
different file name with the -r option:

    shub deploy-reqs -r myreqs.txt

The requirements file must be in a format parsable by pip.
"""

SHORT_HELP = "[DEPRECATED] Build and deploy eggs from requirements.txt"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
@click.option("-r", "--requirements-file", default='requirements.txt',
              type=click.STRING)
def cli(target, requirements_file):
    click.secho(
        "deploy-reqs was deprecated, define a requirements file in your "
        "scrapinghub.yml instead. See {}".format(DEPLOY_DOCS_LINK),
        err=True, fg='yellow',
    )
    main(target, requirements_file)


def main(target, requirements_file):
    targetconf = get_target_conf(target)
    requirements_full_path = os.path.abspath(requirements_file)
    eggs_tmp_dir = _mk_and_cd_eggs_tmpdir()
    _download_egg_files(eggs_tmp_dir, requirements_full_path)
    decompress_egg_files()
    build_and_deploy_eggs(targetconf.project_id, targetconf.endpoint,
                          targetconf.apikey)


def _mk_and_cd_eggs_tmpdir():
    tmpdir = tempfile.mkdtemp(prefix="eggs")
    os.chdir(tmpdir)
    os.mkdir('eggs')
    os.chdir('eggs')
    return os.path.join(tmpdir, 'eggs')


def _download_egg_files(eggs_dir, requirements_file):
    editable_src_dir = tempfile.mkdtemp(prefix='pipsrc')

    click.echo('Downloading eggs...')
    try:
        download_from_pypi(eggs_dir, reqfile=requirements_file,
                           extra_args=["--src", editable_src_dir])
    finally:
        shutil.rmtree(editable_src_dir, ignore_errors=True)
