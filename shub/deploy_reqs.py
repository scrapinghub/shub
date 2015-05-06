import click
import os
import tempfile

from glob import glob
from os.path import isdir

from shub.click_utils import log
from shub.utils import run
from shub import deploy_egg

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
    _decompress_egg_files()
    _build_and_deploy_eggs(project_id)


def _mk_and_cd_eggs_tmpdir():
    tmpdir = tempfile.mkdtemp(prefix="eggs")
    os.chdir(tmpdir)
    os.mkdir('eggs')
    os.chdir('eggs')
    return os.path.join(tmpdir, 'eggs')


def _download_egg_files(eggs_dir, requirements_file):
    pip_cmd = "pip install -d %s -r %s --no-deps --no-use-wheel"
    print(run(pip_cmd % (eggs_dir, requirements_file)))


def _decompress_egg_files():
    decompressor_by_ext = _build_decompressor_by_ext_map()
    eggs = (f for ext in decompressor_by_ext for f in glob('*.%s' % ext))

    for egg in eggs:
        log("Uncompressing: %s" % egg)
        run("%s %s" % (decompressor_by_ext[_ext(egg)], egg))


def _build_and_deploy_eggs(project_id):
    egg_dirs = (f for f in glob('*') if isdir(f))

    for egg_dir in egg_dirs:
        os.chdir(egg_dir)
        deploy_egg.main(project_id)
        os.chdir('..')


def _build_decompressor_by_ext_map():
    unzip = 'unzip -q'
    targz = 'tar zxf'

    return {'zip': unzip,
            'whl': unzip,
            'gz': targz}


def _ext(file_path):
    return os.path.splitext(file_path)[1].strip('.')
