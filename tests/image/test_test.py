import mock
import pytest
from click.testing import CliRunner
from shub import exceptions as shub_exceptions
from shub.image.test import cli

from shub.image.test import _run_docker_command
from shub.image.test import _check_image_exists
from shub.image.test import _check_start_crawl_entry
from shub.image.test import _check_sh_entrypoint

from .utils import FakeProjectDirectory
from .utils import add_sh_fake_config


class MockedNotFound(Exception):
    """Mocking docker.errors.NotFound"""


@pytest.fixture
def docker_client():
    client = mock.Mock()
    client.create_container.return_value = {'Id': '12345'}
    client.wait.return_value = 0
    client.logs.return_value = 'some-logs'
    return client


def test_test_cli(monkeypatch, docker_client):
    """ This test mocks docker library to test the function itself """
    monkeypatch.setattr('docker.errors.NotFound', MockedNotFound)
    monkeypatch.setattr('shub.image.utils.get_docker_client',
                        lambda *args, **kwargs: docker_client)
    with FakeProjectDirectory() as tmpdir:
        add_sh_fake_config(tmpdir)
        runner = CliRunner()
        result = runner.invoke(
            cli, ["dev", "-d", "--version", "test"])
        assert result.exit_code == 0


def test_check_image_exists(monkeypatch, docker_client):
    assert _check_image_exists('img', docker_client) is None

    monkeypatch.setattr('docker.errors.NotFound', MockedNotFound)
    docker_client.inspect_image.side_effect = MockedNotFound
    with pytest.raises(shub_exceptions.NotFoundException):
        _check_image_exists('image', docker_client)


def test_check_sh_entrypoint(docker_client):
    # scrapy/sh-ep-scrapy exists, everything is fine
    assert _check_sh_entrypoint('image', docker_client) is None
    docker_client.create_container.assert_has_calls([
        mock.call(image='image', command=['pip', 'show', 'Scrapy']),
        mock.call(image='image', command=[
            'pip', 'show', 'scrapinghub-entrypoint-scrapy'])])

    # scrapy is here, but no sh-ep-scrapy (failed command)
    docker_client.wait.side_effect = [0, 1]
    with pytest.raises(shub_exceptions.NotFoundException):
        _check_sh_entrypoint('image', docker_client)
    # scrapy is here, but no sh-ep-scrapy (no logs)
    docker_client.wait.side_effect = [0, 0]
    docker_client.logs.side_effect = ['some-log', '']
    with pytest.raises(shub_exceptions.NotFoundException):
        _check_sh_entrypoint('image', docker_client)

    # no scrapy -> nothing to check
    docker_client.wait.side_effect = [1, 0]
    docker_client.logs.side_effect = ['error', 'logs']
    _check_sh_entrypoint('image', docker_client)


def test_start_crawl(docker_client):
    assert _check_start_crawl_entry('image', docker_client) is None
    docker_client.create_container.assert_called_with(
        image='image', command=['which', 'start-crawl'])
    docker_client.wait.return_value = 1
    with pytest.raises(shub_exceptions.NotFoundException):
        _check_start_crawl_entry('image', docker_client)

    docker_client.wait.return_value = 0
    docker_client.logs.return_value = ''
    with pytest.raises(shub_exceptions.NotFoundException):
        _check_start_crawl_entry('image', docker_client)


def test_run_docker_command(docker_client):
    assert _run_docker_command(
        docker_client, 'image-name', ['some', 'cmd']) == \
            (0, 'some-logs')
    docker_client.create_container.assert_called_with(
        image='image-name', command=['some', 'cmd'])
    docker_client.start.assert_called_with({'Id': '12345'})
    docker_client.wait.assert_called_with(container='12345')
    docker_client.logs.assert_called_with(
        container='12345', stdout=True, stderr=False,
        stream=False, timestamps=False)
    docker_client.remove_container.assert_called_with({'Id': '12345'})
