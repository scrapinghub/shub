import os
import sys
import mock
from click.testing import CliRunner
from unittest import TestCase
from shub import exceptions as shub_exceptions
from shub_image.test import cli

from shub_image.test import _run_docker_command
from shub_image.test import _check_image_exists
from shub_image.test import _check_start_crawl_entry
from shub_image.test import _check_sh_entrypoint

from .utils import FakeProjectDirectory
from .utils import add_sh_fake_config


class MockedNotFound(Exception):
    """Mocking docker.errors.NotFound"""


def _mock_docker_errors_module():
    """ A helper to avoid using docker library at all"""
    orig_import = __import__
    errors_mock = mock.Mock()
    errors_mock.NotFound = MockedNotFound
    def import_mock(name, *args):
        if name == 'docker.errors':
            return errors_mock
        return orig_import(name, *args)
    return import_mock


class TestTestCli(TestCase):

    @mock.patch('shub_image.utils.get_docker_client')
    def test_cli(self, mocked_method):
        """ This test mocks docker library to test the function itself """
        client = mock.Mock()
        # mainly for several checks on status & logs
        client.create_container.return_value = {'Id': '12345'}
        client.wait.return_value = 0
        client.logs.return_value = 'some-logs'
        mocked_method.return_value = client
        # patching built-in import to use fake docker.errors
        import_mock = _mock_docker_errors_module()
        with mock.patch('__builtin__.__import__', side_effect=import_mock):
            with FakeProjectDirectory() as tmpdir:
                add_sh_fake_config(tmpdir)
                runner = CliRunner()
                result = runner.invoke(
                    cli, ["dev", "-d", "--version", "test"])
                assert result.exit_code == 0


class TestTestTools(TestCase):

    def setUp(self):
        self.client = mock.Mock()
        self.client.create_container.return_value = {'Id': '12345'}
        self.client.wait.return_value = 0
        self.client.logs.return_value = 'some-logs'

    def test_check_image_exists(self):
        """ This test mocks docker library to test the function itself """
        # patching built-in import to use fake docker.errors
        import_mock = _mock_docker_errors_module()
        with mock.patch('__builtin__.__import__', side_effect=import_mock):
            assert _check_image_exists('img', self.client, True) == None
            self.client.inspect_image.side_effect = MockedNotFound()
            self.assertRaises(shub_exceptions.NotFoundException,
                _check_image_exists, 'image', self.client, True)

    def test_check_sh_entrypoint(self):
        assert _check_sh_entrypoint('image', self.client, True) == None
        self.client.create_container.assert_called_with(
            image='image',
            command=['pip', 'show', 'scrapinghub-entrypoint-scrapy'])
        self.client.wait.return_value = 1
        self.assertRaises(shub_exceptions.NotFoundException,
            _check_sh_entrypoint, 'image', self.client, True)
        self.client.wait.return_value = 0
        self.client.logs.return_value = ''
        self.assertRaises(shub_exceptions.NotFoundException,
            _check_sh_entrypoint, 'image', self.client, True)

    def test_start_crawl(self):
        assert _check_start_crawl_entry('image', self.client, True) == None
        self.client.create_container.assert_called_with(
            image='image', command=['which', 'start-crawl'])
        self.client.wait.return_value = 1
        self.assertRaises(shub_exceptions.NotFoundException,
            _check_start_crawl_entry, 'image', self.client, True)
        self.client.wait.return_value = 0
        self.client.logs.return_value = ''
        self.assertRaises(shub_exceptions.NotFoundException,
            _check_start_crawl_entry, 'image', self.client, True)

    def test_run_docker_command(self):
        assert _run_docker_command(
            self.client, 'image-name', ['some', 'cmd'], True) == \
                (0, 'some-logs')
        self.client.create_container.assert_called_with(
            image='image-name', command=['some', 'cmd'])
        self.client.start.assert_called_with({'Id': '12345'})
        self.client.wait.assert_called_with(container='12345')
        self.client.logs.assert_called_with(
            container='12345', stdout=True, stderr=False,
            stream=False, timestamps=False)
