import mock
from click.testing import CliRunner
from unittest import TestCase
from shub import exceptions as shub_exceptions
from shub_image.push import cli

from .utils import FakeProjectDirectory
from .utils import add_sh_fake_config


@mock.patch('shub_image.utils.get_docker_client')
class TestPushCli(TestCase):

    def test_cli_with_apikey_login(self, mocked_method):
        mocked = mock.MagicMock()
        mocked.login.return_value = {"Status": "Login Succeeded"}
        mocked.push.return_value = [
            {"stream": "In process"},
            {"status": "Successfully pushed"}]
        mocked_method.return_value = mocked
        with FakeProjectDirectory() as tmpdir:
            add_sh_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(cli, ["dev", "--version", "test"])
            assert result.exit_code == 0
            mocked.push.assert_called_with(
                'registry/user/project:test', decode=True,
                insecure_registry=False, stream=True)

    def test_cli_with_custom_login(self, mocked_method):
        mocked = mock.MagicMock()
        mocked.login.return_value = {"Status": "Login Succeeded"}
        mocked.push.return_value = [
            {"stream": "In process"},
            {"status": "Successfully pushed"}]
        mocked_method.return_value = mocked
        with FakeProjectDirectory() as tmpdir:
            add_sh_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(
                cli, ["dev", "--version", "test", "--username", "user",
                      "--password", "pass", "--email", "mail"])
            assert result.exit_code == 0
            mocked.login.assert_called_with(
                email=u'mail', password=u'pass',
                reauth=False, registry='registry', username=u'user')
            mocked.push.assert_called_with(
                'registry/user/project:test', decode=True,
                insecure_registry=False, stream=True)

    def test_cli_with_insecure_registry(self, mocked_method):
        mocked = mock.MagicMock()
        mocked.login.return_value = {"Status": "Login Succeeded"}
        mocked.push.return_value = [
            {"stream": "In process"},
            {"status": "Successfully pushed"}]
        mocked_method.return_value = mocked
        with FakeProjectDirectory() as tmpdir:
            add_sh_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(
                cli, ["dev", "--version", "test", "--insecure"])
            assert result.exit_code == 0
            assert not mocked.login.called
            mocked.push.assert_called_with(
                'registry/user/project:test', decode=True,
                insecure_registry=True, stream=True)

    def test_cli_with_login_username_only(self, mocked_method):
        mocked = mock.MagicMock()
        mocked.login.return_value = {"Status": "Login Succeeded"}
        mocked.push.return_value = [
            {"stream": "In process"},
            {"status": "Successfully pushed"}]
        mocked_method.return_value = mocked
        with FakeProjectDirectory() as tmpdir:
            add_sh_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(
                cli, ["dev", "--version", "test", "--apikey", "apikey"])
            assert result.exit_code == 0
            mocked.login.assert_called_with(
                email=None, password=' ',
                reauth=False, registry='registry', username='apikey')
            mocked.push.assert_called_with(
                'registry/user/project:test', decode=True,
                insecure_registry=False, stream=True)

    def test_cli_login_fail(self, mocked_method):
        mocked = mock.MagicMock()
        mocked.login.return_value = {"Status": "Login Failed!"}
        mocked_method.return_value = mocked
        with FakeProjectDirectory() as tmpdir:
            add_sh_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(
                cli, ["dev", "--version", "test", "--username", "user",
                      "--password", "pass", "--email", "mail"])
            assert result.exit_code == \
                shub_exceptions.RemoteErrorException.exit_code

    def test_cli_push_fail(self, mocked_method):
        mocked = mock.MagicMock()
        mocked.login.return_value = {"Status": "Login Succeeded"}
        mocked.push.return_value = [{"error": "Failed:(", "errorDetail": ""}]
        mocked_method.return_value = mocked
        with FakeProjectDirectory() as tmpdir:
            add_sh_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(
                cli, ["dev", "--version", "test", "--username", "user",
                      "--password", "pass", "--email", "mail"])
            assert result.exit_code == \
                shub_exceptions.RemoteErrorException.exit_code
