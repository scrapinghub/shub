import os

import pytest


@pytest.fixture
def tempdir(tmpdir):
    cwd = os.getcwd()
    os.chdir(str(tmpdir))
    yield tmpdir
    os.chdir(cwd)
