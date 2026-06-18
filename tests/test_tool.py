import os
from unittest import mock

import pytest
from click.testing import CliRunner

from shub.tool import _load_dotenv_apikey, cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def no_update_check():
    # Avoid network calls from the cli group callback during tests.
    with mock.patch('shub.tool.update_available', return_value=None):
        yield


def test_load_dotenv_apikey_default_path(tmp_path, monkeypatch):
    monkeypatch.delenv('SHUB_APIKEY', raising=False)
    (tmp_path / '.env').write_text('SHUB_APIKEY=FROMDOTENV\n')
    monkeypatch.chdir(tmp_path)

    _load_dotenv_apikey(None)

    assert os.environ['SHUB_APIKEY'] == 'FROMDOTENV'


def test_load_dotenv_apikey_parent_dir(tmp_path, monkeypatch):
    monkeypatch.delenv('SHUB_APIKEY', raising=False)
    (tmp_path / '.env').write_text('SHUB_APIKEY=FROMPARENT\n')
    subdir = tmp_path / 'project' / 'subdir'
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)

    _load_dotenv_apikey(None)

    assert os.environ['SHUB_APIKEY'] == 'FROMPARENT'


def test_load_dotenv_apikey_custom_path(tmp_path, monkeypatch):
    monkeypatch.delenv('SHUB_APIKEY', raising=False)
    env_file = tmp_path / 'custom.env'
    env_file.write_text('SHUB_APIKEY=CUSTOMKEY\n')

    _load_dotenv_apikey(str(env_file))

    assert os.environ['SHUB_APIKEY'] == 'CUSTOMKEY'


def test_load_dotenv_apikey_only_reads_apikey(tmp_path, monkeypatch):
    monkeypatch.delenv('SHUB_APIKEY', raising=False)
    monkeypatch.delenv('OTHER_VAR', raising=False)
    env_file = tmp_path / 'custom.env'
    env_file.write_text('SHUB_APIKEY=ONLYTHIS\nOTHER_VAR=ignored\n')

    _load_dotenv_apikey(str(env_file))

    assert os.environ['SHUB_APIKEY'] == 'ONLYTHIS'
    assert 'OTHER_VAR' not in os.environ


def test_existing_env_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv('SHUB_APIKEY', 'FROMENV')
    env_file = tmp_path / 'custom.env'
    env_file.write_text('SHUB_APIKEY=FROMDOTENV\n')

    _load_dotenv_apikey(str(env_file))

    assert os.environ['SHUB_APIKEY'] == 'FROMENV'


def test_missing_dotenv_file_is_noop(tmp_path, monkeypatch):
    monkeypatch.delenv('SHUB_APIKEY', raising=False)

    _load_dotenv_apikey(str(tmp_path / 'does-not-exist.env'))

    assert 'SHUB_APIKEY' not in os.environ


def test_cli_dotenv_path_option(runner, tmp_path, monkeypatch):
    monkeypatch.delenv('SHUB_APIKEY', raising=False)
    env_file = tmp_path / 'custom.env'
    env_file.write_text('SHUB_APIKEY=CLIKEY\n')

    result = runner.invoke(cli, ['--dotenv-path', str(env_file), 'version'])

    assert result.exit_code == 0, result.output
    assert os.environ['SHUB_APIKEY'] == 'CLIKEY'
