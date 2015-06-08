import click
import os
import tempfile

from shub.utils import run, decompress_egg_files
from shub import utils


@click.command(help="Build and deploy eggs from requirements.txt")
@click.argument("project_id", required=True)
@click.argument("requirements_file", required=True)
def cli(project_id, requirements_file):
    """Just a wrapper around the deploy_egg module"""
    main(project_id, requirements_file)


def main(project_id, requirements_file):
    requirements_full_path = os.path.abspath(requirements_file)
    eggs_tmp_dir = _mk_and_cd_eggs_tmpdir()
    _download_egg_files(eggs_tmp_dir, requirements_full_path)
    decompress_egg_files()
    utils.build_and_deploy_eggs(project_id)


def _mk_and_cd_eggs_tmpdir():
    tmpdir = tempfile.mkdtemp(prefix="eggs")
    os.chdir(tmpdir)
    os.mkdir('eggs')
    os.chdir('eggs')
    return os.path.join(tmpdir, 'eggs')


def _download_egg_files(eggs_dir, requirements_file):
    pip_cmd = "pip install -d %s -r %s --no-deps --no-use-wheel"
    print(run(pip_cmd % (eggs_dir, requirements_file)))
