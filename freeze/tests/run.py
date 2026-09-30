import os
import re
import shlex
import shutil
import tempfile
from pathlib import Path
from subprocess import PIPE, Popen

import pytest

from . import fakeserver

SHUB = str((Path(__file__).parent / "../../dist_bin/shub").resolve())


@pytest.fixture(scope="module")
def apipipe():
    return fakeserver.run(("127.0.0.1", 7999))


@pytest.fixture
def scrapyproject():
    cwd = Path.cwd()
    tmpdir = str(Path(tempfile.mkdtemp(), "project"))
    shutil.copytree(Path(__file__).parent.resolve() / "testproject", tmpdir)
    os.chdir(tmpdir)
    yield tmpdir
    os.chdir(cwd)
    shutil.rmtree(tmpdir, ignore_errors=True)


def shub(shub_args):
    cmd = [SHUB]
    if isinstance(shub_args, str):
        shub_args = shlex.split(shub_args)
    if shub_args is not None:
        cmd.extend(shub_args)
    return Popen(cmd, stdout=PIPE, stderr=PIPE)  # noqa: S603


def test_version():
    stdout, _stderr = shub("version").communicate()
    assert re.match(rb"\d+[.]\d+[.]\d+$", stdout.strip())


def test_deploy_without_project():
    stdout, stderr = shub("deploy").communicate()
    assert stdout == b""
    assert b"Cannot find project" in stderr


def test_deploy_default_project(apipipe, scrapyproject):
    p = shub("deploy")
    assert apipipe.poll(15)
    req = apipipe.recv()
    assert req["path"] == "/api/scrapyd/addversion.json"
    apipipe.send((200, None, {"status": "ok"}))
    stdout, _stderr = p.communicate()
    assert b'{"status": "ok"}' in stdout
