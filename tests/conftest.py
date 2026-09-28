import pytest


@pytest.fixture
def tempdir(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    return tmpdir
