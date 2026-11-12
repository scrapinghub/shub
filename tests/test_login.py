import textwrap
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from click.testing import CliRunner
from yaml import CLoader as Loader

from shub import login
from shub.config import ShubConfig
from shub.exceptions import AlreadyLoggedInException

from .utils import AssertInvokeRaisesMixin

VALID_KEY = 32 * "1"


@patch("shub.login.GLOBAL_SCRAPINGHUB_YML_PATH", new=".scrapinghub.yml")
@patch("shub.config.GLOBAL_SCRAPINGHUB_YML_PATH", new=".scrapinghub.yml")
class LoginTest(AssertInvokeRaisesMixin, unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def _run(self, user_input=VALID_KEY, files=None, fs=None, **kwargs):
        """Invokes the login cli on an isolated filesystem"""

        def write_local_test_files():
            for path, content in (files or {}).items():
                with Path(path).open("w") as f:
                    f.write(content)

        def invoke():
            return self.runner.invoke(login.cli, input=user_input, **kwargs)

        def run():
            write_local_test_files()
            with patch.object(login, "_is_valid_apikey", return_value=True):
                return invoke()

        if fs:
            return run()

        with self.runner.isolated_filesystem():
            return run()

    def test_write_key_to_new_file(self):
        with self.runner.isolated_filesystem() as fs:
            self._run(fs=fs)
            with Path(".scrapinghub.yml").open() as f:
                conf = yaml.load(f, Loader=Loader)
            assert conf["apikeys"]["default"] == VALID_KEY

    def test_write_key_to_existing_file(self):
        VALID_SCRAPINGHUB_YML = textwrap.dedent("""
            endpoints:
                other: some_endpoint
        """)
        with self.runner.isolated_filesystem() as fs:
            files = {".scrapinghub.yml": VALID_SCRAPINGHUB_YML}
            self._run(files=files, fs=fs)
            with Path(".scrapinghub.yml").open() as f:
                conf = yaml.load(f, Loader=Loader)
            assert conf["apikeys"]["default"] == VALID_KEY
            assert conf["endpoints"]["other"] == "some_endpoint"

    def test_suggest_project_key(self):
        PROJECT_SH_YML = textwrap.dedent("""
            apikeys:
                default: KEY_SUGGESTION
        """)
        files = {"scrapinghub.yml": PROJECT_SH_YML}
        result = self._run(files=files)
        err = f"Unexpected output: {result.output}"
        assert "KEY_SUGGESTION" in result.output, err

    def test_suggest_env_key(self):
        result = self._run(env={"SHUB_APIKEY": "SHUB_APIKEY_VALUE"})
        err = f"Unexpected output: {result.output}"
        assert "SHUB_APIKEY_VALUE" in result.output, err

    def test_use_suggestion_to_log_in(self):
        apikey_suggestion = "SHUB_APIKEY_VALUE"
        with self.runner.isolated_filesystem() as fs:
            self._run(
                env={"SHUB_APIKEY": apikey_suggestion},
                user_input="\n",
                fs=fs,
            )
            with Path(".scrapinghub.yml").open() as f:
                conf = yaml.load(f, Loader=Loader)
            assert conf["apikeys"]["default"] == apikey_suggestion

    def test_login_attempt_after_login_doesnt_lead_to_an_error(self):
        with self.runner.isolated_filesystem() as fs:
            self._run(fs=fs)
            self.assertInvokeRaises(
                AlreadyLoggedInException, login.cli, input=VALID_KEY
            )

    def test_write_key_for_project_endpoint(self):
        PROJECT_SH_YML = textwrap.dedent("""
            endpoint: https://example.com/api/
        """)
        GLOBAL_SH_YML = textwrap.dedent("""
            apikeys:
                default: ZYTE_KEY
        """)
        with self.runner.isolated_filesystem():
            for path, content in (
                ("scrapinghub.yml", PROJECT_SH_YML),
                (".scrapinghub.yml", GLOBAL_SH_YML),
            ):
                with Path(path).open("w") as f:
                    f.write(content)
            with patch.object(
                login, "_is_valid_apikey", return_value=True
            ) as mock_valid:
                self.runner.invoke(login.cli, input=VALID_KEY)
            mock_valid.assert_called_once_with(
                VALID_KEY, endpoint="https://example.com/api/"
            )
            with Path(".scrapinghub.yml").open() as f:
                conf = yaml.load(f, Loader=Loader)
            assert conf["apikeys"] == {
                "default": "ZYTE_KEY",
                "https://example.com/api/": VALID_KEY,
            }


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (200, True),
        (401, False),
    ],
)
@pytest.mark.parametrize(
    ("endpoint", "expected_url"),
    [
        (None, ShubConfig.DEFAULT_ENDPOINT + "v2/users/me"),
        ("https://example.com/api/", "https://example.com/api/v2/users/me"),
    ],
)
def test_is_valid_apikey(status_code, expected, endpoint, expected_url):
    with patch("shub.login.requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=status_code)
        assert login._is_valid_apikey("KEY", endpoint=endpoint) is expected
    mock_get.assert_called_once_with(expected_url, params={"apikey": "KEY"})


@patch("shub.login.GLOBAL_SCRAPINGHUB_YML_PATH", new=".scrapinghub.yml")
@patch("shub.config.GLOBAL_SCRAPINGHUB_YML_PATH", new=".scrapinghub.yml")
def test_retry_after_invalid_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch.object(
        login, "_is_valid_apikey", side_effect=[False, True]
    ) as mock_valid:
        result = CliRunner().invoke(login.cli, input=f"INVALID_KEY\n{VALID_KEY}\n")
    assert "API key failed, try again." in result.output
    assert mock_valid.call_count == 2
    with (tmp_path / ".scrapinghub.yml").open() as f:
        conf = yaml.load(f, Loader=Loader)
    assert conf["apikeys"]["default"] == VALID_KEY
