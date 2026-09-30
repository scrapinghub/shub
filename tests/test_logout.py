import textwrap
import unittest
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from shub import config, logout


@mock.patch("shub.config.GLOBAL_SCRAPINGHUB_YML_PATH", new=".scrapinghub.yml")
@mock.patch("shub.config.NETRC_PATH", new=".netrc")
@mock.patch("shub.logout.GLOBAL_SCRAPINGHUB_YML_PATH", new=".scrapinghub.yml")
class LogoutTestCase(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_remove_key(self):
        GLOBAL_SH_YML = textwrap.dedent("""
            apikeys:
                default: LOGGED_IN_KEY
        """)
        with self.runner.isolated_filesystem():
            with Path(".scrapinghub.yml").open("w") as f:
                f.write(GLOBAL_SH_YML)
            conf = config.load_shub_config()
            assert "default" in conf.apikeys
            self.runner.invoke(logout.cli)
            conf = config.load_shub_config()
            assert "default" not in conf.apikeys

    @mock.patch("shub.logout.update_yaml_dict")
    def test_fail_on_not_logged_in(self, mock_uyd):
        with self.runner.isolated_filesystem():
            self.runner.invoke(logout.cli)
            assert not mock_uyd.called
