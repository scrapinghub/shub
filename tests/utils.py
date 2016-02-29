import os
import shutil
import tempfile
from contextlib import contextmanager


@contextmanager
def FakeProjectDirectory():
    tmpdir = tempfile.mkdtemp()
    current = os.getcwd()
    os.chdir(tmpdir)
    try:
        yield tmpdir
    finally:
        os.chdir(current)
        shutil.rmtree(tmpdir)

def add_scrapy_fake_config(tmpdir):
    # add fake scrapy.cfg
    config_path = os.path.join(tmpdir, 'scrapy.cfg')
    with open(config_path, 'w') as config_file:
        config_file.write("[settings]\ndefault=test.settings")


def add_sh_fake_config(tmpdir):
    # add fake SH config
    sh_config_path = os.path.join(tmpdir, 'scrapinghub.yml')
    with open(sh_config_path, 'w') as sh_config_file:
        sh_config_file.write('\n'.join([
            "projects:", "  dev: 12345",
            "images:", "  dev: registry/user/project",
            "endpoints:", "  dev: https://dash-fake",
            "apikeys:", "  default: abcdef",
            "version: GIT"]))


def add_fake_requirements(tmpdir):
    """Add fake requirements"""
    reqs_path = os.path.join(tmpdir, 'fake-requirements.txt')
    with open(reqs_path, 'w') as reqs_file:
        reqs_file.write("mock\nrequests")


def add_fake_dockerfile(tmpdir):
    """Add fake Dockerfile"""
    docker_path = os.path.join(tmpdir, 'Dockerfile')
    with open(docker_path, 'w') as docker_file:
        docker_file.write("FROM python:2.7")


def add_fake_setup_py(tmpdir):
    """Add fake setup.py for extract scripts tests"""
    setup_path = os.path.join(tmpdir, 'setup.py')
    with open(setup_path, 'w') as setup_file:
        setup_file.write('\n'.join([
            "from setuptools import setup",
            "setup(name = 'project', version = '1.0',",
            "entry_points = {'scrapy': ['settings = test.settings']},",
            "scripts = ['bin/scriptA.py', 'scriptB.py'])"
        ]))
