from __future__ import print_function
import click
import os
import tempfile
import shutil

from shub.utils import run, decompress_egg_files
from shub.click_utils import log
from shub import utils
from shub import scrapycfg
from shub.auth import find_api_key


@click.command(help="Build and deploy eggs from requirements.txt")
@click.option("-p", "--project", help="the project ID to deploy to",
              type=click.INT)
@click.argument("requirements_file", required=True)
def cli(project, requirements_file):
    """Just a wrapper around the deploy_egg module"""
    main(project, requirements_file)


def main(project_id, requirements_file):
    target = scrapycfg.get_target('default')
    project_id = scrapycfg.get_project(target, project_id)
    apikey = find_api_key()
    requirements_full_path = os.path.abspath(requirements_file)
    eggs_tmp_dir = _mk_and_cd_eggs_tmpdir()
    _download_egg_files(eggs_tmp_dir, requirements_full_path)
    decompress_egg_files()
    utils.build_and_deploy_eggs(project_id, apikey)


def _mk_and_cd_eggs_tmpdir():
    tmpdir = tempfile.mkdtemp(prefix="eggs")
    os.chdir(tmpdir)
    os.mkdir('eggs')
    os.chdir('eggs')
    return os.path.join(tmpdir, 'eggs')


def _download_egg_files(eggs_dir, requirements_file):
    editable_src_dir = tempfile.mkdtemp(prefix='pipsrc')

    log('Downloading eggs...')
    try:
        pip_cmd = ("pip install -d {eggs_dir} -r {requirements_file}"
                   " --src {editable_src_dir} --no-deps --no-use-wheel")
        log(run(pip_cmd.format(eggs_dir=eggs_dir,
                               editable_src_dir=editable_src_dir,
                               requirements_file=requirements_file)))
    finally:
        shutil.rmtree(editable_src_dir, ignore_errors=True)
