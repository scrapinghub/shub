import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

SH_CONFIG_FILE = """
projects:
  dev:
    id: 12345
    image: registry.io/user/project
  xyz:
    id: 32167
    image: images.scrapinghub.com/project/32167
endpoints:
  dev: https://dash-fake
apikeys:
  default: abcdef
"""

SH_SETUP_FILE = """
from setuptools import setup
setup(
    name = 'project', version = '1.0',
    entry_points = {'scrapy': ['settings = test.settings']},
    scripts = ['bin/scriptA.py', 'scriptB.py']
)
"""


@contextmanager
def FakeProjectDirectory():
    tmpdir = os.path.realpath(tempfile.mkdtemp())
    current = Path.cwd()
    os.chdir(tmpdir)
    try:
        yield tmpdir
    finally:
        os.chdir(current)
        shutil.rmtree(tmpdir)


def add_scrapy_fake_config(tmpdir):
    # add fake scrapy.cfg
    Path(tmpdir, "scrapy.cfg").write_text("[settings]\ndefault=test.settings")


def add_sh_fake_config(tmpdir):
    # add fake SH config
    Path(tmpdir, "scrapinghub.yml").write_text(SH_CONFIG_FILE)


def add_fake_requirements(tmpdir):
    """Add fake requirements"""
    Path(tmpdir, "fake-requirements.txt").write_text("mock\nrequests")


def add_fake_dockerfile(tmpdir):
    """Add fake Dockerfile"""
    Path(tmpdir, "Dockerfile").write_text("FROM python:2.7")


def add_fake_setup_py(tmpdir):
    """Add fake setup.py for extract scripts tests"""
    Path(tmpdir, "setup.py").write_text(SH_SETUP_FILE)
