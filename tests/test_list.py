import mock
from click.testing import CliRunner
from unittest import TestCase

from shub_image.list import cli
from shub_image.list import _run_list_cmd

from .utils import FakeProjectDirectory
from .utils import add_sh_fake_config


class TestListCli(TestCase):

    def test_cli_no_sh_config(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["dev", "-d", "--version", "test"])
        assert result.exit_code == 69
        assert 'Could not find image for dev' in result.output

    @mock.patch('shub_image.utils.get_docker_client')
    @mock.patch('requests.get')
    def test_cli_no_project(self, get_mocked, get_client_mock):
        client_mock = mock.Mock()
        client_mock.create_container.return_value = {'Id': '1234'}
        client_mock.wait.return_value = 0
        client_mock.logs.return_value = b'abc\ndef'
        get_client_mock.return_value = client_mock

        with FakeProjectDirectory() as tmpdir:
            add_sh_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(cli, ["xyz", "--version", "test"])
            assert result.exit_code == 0
            assert result.output.endswith('abc\ndef\n')
        assert not get_mocked.called

    @mock.patch('shub_image.utils.get_docker_client')
    @mock.patch('requests.get')
    def test_cli_container_error(self, get_mocked, get_client_mock):
        client_mock = mock.Mock()
        client_mock.create_container.return_value = {'Id': '1234'}
        client_mock.wait.return_value = 66
        get_client_mock.return_value = client_mock

        get_settings_mock = mock.Mock()
        get_settings_mock.json.return_value = {}
        get_mocked.return_value = get_settings_mock

        with FakeProjectDirectory() as tmpdir:
            add_sh_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(cli, ["dev", "-d", "--version", "test"])
            assert result.exit_code == 1
            assert 'list cmd exited with code 66' in result.output

    @mock.patch('shub_image.utils.get_docker_client')
    @mock.patch('requests.get')
    def test_cli(self, get_mocked, get_client_mock):
        client_mock = mock.Mock()
        client_mock.create_container.return_value = {'Id': '1234'}
        client_mock.wait.return_value = 0
        client_mock.logs.return_value = b'abc\ndef\ndsd'
        get_client_mock.return_value = client_mock

        get_settings_mock = mock.Mock()
        get_settings_mock.json.return_value = {}
        get_mocked.return_value = get_settings_mock

        with FakeProjectDirectory() as tmpdir:
            add_sh_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(cli, [
                "dev", "-d", "-s", "--version", "test"])
            assert result.exit_code == 0
            assert result.output.endswith('abc\ndef\ndsd\n')
        get_mocked.assert_called_with(
            'https://app.scrapinghub.com/api/settings/get.json',
            allow_redirects=False, auth=('abcdef', ''),
            params={'project': 12345}, timeout=300)


class TestListCmd(TestCase):

    @mock.patch('shub_image.utils.get_docker_client')
    def test_run_list_cmd(self, get_client_mock):
        client_mock = mock.Mock()
        client_mock.create_container.return_value = {'Id': '1234'}
        client_mock.wait.return_value = 0
        client_mock.logs.return_value = 'abc\ndef\ndsd'
        get_client_mock.return_value = client_mock
        assert _run_list_cmd(1234, 'image', {})[0] == 0
        client_mock.create_container.assert_called_with(
            command=['list-spiders'], environment={
                'JOB_SETTINGS': '{}',
                'SCRAPY_PROJECT_ID': '1234'}, image='image')
        client_mock.start.assert_called_with({'Id': '1234'})
        client_mock.wait.assert_called_with(container="1234")
        client_mock.logs.assert_called_with(
            container='1234', stderr=False, stdout=True,
            stream=False, timestamps=False)
