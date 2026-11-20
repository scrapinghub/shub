from unittest import TestCase, mock

from click.testing import CliRunner

from shub import exceptions as shub_exceptions
from shub.image import utils
from shub.image.check import cli

from .utils import FakeProjectDirectory


class TestCheckCli(TestCase):
    @mock.patch("requests.get")
    def test_cli(self, mocked):
        # the test creates .releases file locally
        # this context manager cleans it in the end
        with FakeProjectDirectory():
            runner = CliRunner()
            result = runner.invoke(cli, [])
            assert result.exit_code == shub_exceptions.NotFoundException.exit_code
            deploy_id1 = utils.store_status_url("http://linkA", 2)
            deploy_id2 = utils.store_status_url("http://linkB", 2)
            utils.store_status_url("http://linkC", 2)

            # get latest (deploy 3)
            result = runner.invoke(cli, [])
            assert result.exit_code == 0
            mocked.assert_called_with("http://linkC", timeout=300)

            # get deploy by id
            result = runner.invoke(cli, ["--id", deploy_id2])
            assert result.exit_code == 0
            mocked.assert_called_with("http://linkB", timeout=300)

            # get non-existing deploy
            result = runner.invoke(cli, ["--id", deploy_id1])
            assert result.exit_code == shub_exceptions.NotFoundException.exit_code

    @mock.patch("requests.get")
    def test_cli_escapes_a_string_status_body(self, mocked):
        mocked.return_value.json.return_value = "ok\x1b]0;title\x07\rfake"
        with FakeProjectDirectory():
            utils.store_status_url("http://linkA", 2)
            result = CliRunner().invoke(cli, [])
        assert result.exit_code == 0
        assert not any(c in result.output for c in "\x1b\x07\r")
        assert "Deploy results: 'ok\\x1b]0;title\\x07\\rfake'" in result.output
