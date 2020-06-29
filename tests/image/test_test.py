import mock
import pytest
from click.testing import CliRunner
from shub import exceptions as shub_exceptions
from shub.image.test import (
    cli, _run_docker_command, _check_image_size, _check_start_crawl_entry,
    IMAGE_SIZE_LIMIT,
)

from .utils import FakeProjectDirectory
from .utils import add_sh_fake_config


class MockedNotFound(Exception):
    """Mocking docker.errors.NotFound"""


@pytest.fixture
def docker_client():
    client = mock.Mock()
    client.create_container.return_value = {'Id': '12345'}
    client.wait.return_value = {'Error': None, 'StatusCode': 0}
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
            cli, ["dev", "-v", "--version", "test"])
        assert result.exit_code == 0


def test_check_image_exists(monkeypatch, docker_client):
    assert _check_image_size('img', docker_client) is None

    monkeypatch.setattr('docker.errors.NotFound', MockedNotFound)
    docker_client.inspect_image.side_effect = MockedNotFound
    with pytest.raises(shub_exceptions.NotFoundException):
        _check_image_size('image', docker_client)


def test_check_image_size(monkeypatch, docker_client):
    docker_client.inspect_image.return_value = {'Size': IMAGE_SIZE_LIMIT}
    assert _check_image_size('img', docker_client) is None

    docker_client.inspect_image.return_value = {'Size': IMAGE_SIZE_LIMIT + 1}
    with pytest.raises(shub_exceptions.CustomImageTooLargeException):
        _check_image_size('image', docker_client)


def test_start_crawl(docker_client):
    assert _check_start_crawl_entry('image', docker_client) is None
    docker_client.create_container.assert_called_with(
        image='image', command=['which', 'start-crawl'])
    docker_client.wait.return_value = {'Error': None, 'StatusCode': 1}
    with pytest.raises(shub_exceptions.NotFoundException):
        _check_start_crawl_entry('image', docker_client)

    docker_client.wait.return_value = {'Error': None, 'StatusCode': 0}
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
