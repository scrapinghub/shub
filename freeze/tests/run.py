import os
import re
import shlex
import shutil
import tempfile
from os.path import abspath, dirname, join
from subprocess import Popen, PIPE

import pytest
from . import fakeserver

SHUB = abspath(join(dirname(__file__), '../../dist_bin/shub'))


@pytest.fixture(scope='module')
def apipipe():
    return fakeserver.run(("127.0.0.1", 7999))


@pytest.fixture
def scrapyproject(request):
    cwd = os.getcwd()
    tmpdir = os.path.join(tempfile.mkdtemp(), 'project')
    def _fin():
        os.chdir(cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
    request.addfinalizer(_fin)
    shutil.copytree(abspath(join(dirname(__file__), 'testproject')), tmpdir)
    os.chdir(tmpdir)
    return tmpdir


def shub(shub_args):
    cmd = [SHUB]
    if isinstance(shub_args, str):
        shub_args = shlex.split(shub_args)
    if shub_args is not None:
        cmd.extend(shub_args)
    return Popen(cmd, stdout=PIPE, stderr=PIPE)


def test_version():
    stdout, stderr = shub('version').communicate()
    assert re.match(r'\d+[.]\d+[.]\d+$', stdout.strip())


def test_deploy_without_project():
    stdout, stderr = shub('deploy').communicate()
    assert stdout == b''
    assert b'Error: No Scrapy project found in this location.' in stderr


def test_deploy_default_project(apipipe, scrapyproject):
    p = shub('deploy')
    assert apipipe.poll(15)
    req = apipipe.recv()
    assert req['path'] == '/api/scrapyd/addversion.json'
    apipipe.send((200, None, {'status': 'ok'}))
    stdout, stderr = p.communicate()
    assert '{"status": "ok"}' in stdout
