import json

import docker
import mock
import pytest
from click.testing import CliRunner

from shub.exceptions import BadParameterException, ShubException
from shub.image.list import cli, list_cmd
from shub.image.list import _run_cmd_in_docker_container
from shub.image.list import _extract_metadata_from_image_info_output


def _mock_docker_client(wait_code=0, logs=None):
    client_mock = mock.Mock()
    client_mock.create_container.return_value = {'Id': '1234'}
    client_mock.wait.return_value = wait_code
    client_mock.logs.return_value = logs or ''
    return client_mock


def _get_settings_mock(settings=None):
    settings_mock = mock.Mock()
    settings_mock.json.return_value = settings or {}
    return settings_mock


def test_cli_no_scrapinghub_config():
    result = CliRunner().invoke(cli, ["dev", "-v", "--version", "test"])
    assert result.exit_code == BadParameterException.exit_code
    assert 'Could not find target "dev"' in result.output


@pytest.mark.usefixtures('project_dir')
@mock.patch('shub.image.utils.get_docker_client')
@mock.patch('requests.get')
def test_cli(requests_get_mock, get_docker_client_mock):
    """Case when shub-image-info succeeded."""
    requests_get_mock.return_value = _get_settings_mock()
    mocked_logs = json.dumps({'project_type': 'scrapy', 'spiders': ['abc', 'def']})
    docker_client = _mock_docker_client(logs=mocked_logs)
    get_docker_client_mock.return_value = docker_client
    result = CliRunner().invoke(cli, ["dev", "-v", "-s", "--version", "test"])
    assert result.exit_code == 0
    assert result.output.endswith('abc\ndef\n')
    requests_get_mock.assert_called_with(
        'https://app.scrapinghub.com/api/settings/get.json',
        allow_redirects=False, auth=('abcdef', ''),
        params={'project': 12345}, timeout=300)


@pytest.mark.usefixtures('project_dir')
@mock.patch('shub.image.utils.get_docker_client')
@mock.patch('requests.get')
def test_cli_image_info_error(requests_get_mock, get_docker_client_mock):
    """Case when shub-image-info command failed with unknown exit code."""
    requests_get_mock.return_value = _get_settings_mock()
    docker_client = _mock_docker_client(wait_code=1, logs='some-error')
    get_docker_client_mock.return_value = docker_client
    result = CliRunner().invoke(cli, ["dev", "-v", "--version", "test"])
    assert result.exit_code == 1
    assert 'Container with shub-image-info cmd exited with code 1' in result.output


@pytest.mark.usefixtures('project_dir')
@mock.patch('shub.image.utils.get_docker_client')
@mock.patch('requests.get')
def test_cli_image_info_not_found(requests_get_mock, get_docker_client_mock):
    """Case when shub-image-info cmd not found with fallback to list-spiders."""
    requests_get_mock.return_value = _get_settings_mock({'SETTING': 'VALUE'})
    docker_client = _mock_docker_client()
    docker_client.wait.side_effect = [127, 0]
    docker_client.logs.side_effect = ["not-found", "spider1\nspider2\n"]
    get_docker_client_mock.return_value = docker_client
    result = CliRunner().invoke(cli, ["dev", "-v", "--version", "test"])
    assert result.exit_code == 0
    assert 'spider1\nspider2' in result.output


@pytest.mark.usefixtures('project_dir')
@mock.patch('shub.image.utils.get_docker_client')
@mock.patch('requests.get')
def test_cli_both_commands_failed(requests_get_mock, get_docker_client_mock):
    """Case when shub-image-info cmd not found with fallback to list-spiders."""
    requests_get_mock.return_value = _get_settings_mock({'SETTING': 'VALUE'})
    docker_client = _mock_docker_client(wait_code=127, logs='not-found')
    get_docker_client_mock.return_value = docker_client
    result = CliRunner().invoke(cli, ["dev", "-v", "--version", "test"])
    assert result.exit_code == 1
    assert 'Container with list cmd exited with code 127' in result.output


@mock.patch('shub.image.utils.get_docker_client')
def test_run_cmd_in_docker_container(get_docker_client_mock):
    docker_client = _mock_docker_client(logs='abc\ndef\ndsd')
    get_docker_client_mock.return_value = docker_client
    test_env = {'TEST_ENV1': 'VAL1', 'TEST_ENV2': 'VAL2'}
    result = _run_cmd_in_docker_container('image', 'test-cmd', test_env)
    assert result[0] == 0
    assert result[1] == 'abc\ndef\ndsd'
    docker_client.create_container.assert_called_with(
        command=['test-cmd'], environment=test_env, image='image')
    docker_client.start.assert_called_with({'Id': '1234'})
    docker_client.wait.assert_called_with(container="1234")
    docker_client.logs.assert_called_with(
        container='1234', stderr=False, stdout=True,
        stream=False, timestamps=False)


@mock.patch('shub.image.list._get_project_settings', return_value={})
@mock.patch('shub.image.utils.get_docker_client')
def test_shub_image_info_fallback(get_docker_client_mock, _):
    exception = docker.errors.APIError(
        mock.Mock(),
        mock.Mock(),
        explanation=(
            'Cannot start container xxx: [8] System error: exec: "shub-image-info": '
            'executable file not found in $PATH'
        )
    )
    get_docker_client_mock().create_container.return_value = {'Id': 'id'}
    get_docker_client_mock().start.side_effect = [
        exception,
        None,
    ]
    get_docker_client_mock().wait.return_value = 0
    get_docker_client_mock().logs.return_value = 'abc\ndef\n'
    result = list_cmd('image_name', 111, 'endpoint', 'apikey')
    assert get_docker_client_mock().start.call_count == 2
    assert result == {'spiders': [u'abc', u'def'], 'project_type': 'scrapy'}


@pytest.mark.parametrize('output,error_msg', [
    ('bad-json', 'output is not a valid JSON dict'),
    (['data'], 'output is not a valid JSON dict'),
    ({'spiders': []}, '"project_type" key is required and must be a string'),
    ({'project_type': 1}, '"project_type" key is required and must be a string'),
    ({'project_type': 'scrapy'}, '"spiders" key is required and must be a list'),
    ({'project_type': 'scrapy', 'spiders': 'bad-data'}, '"spiders" key is required and must be a list'),
    ({'project_type': 'scrapy', 'spiders': ['']}, "spider name can't be empty or non-string"),
    ({'project_type': 'scrapy', 'spiders': [123]}, "spider name can't be empty or non-string"),
])
def test_extract_metadata_from_image_info_output_failures(output, error_msg):
    with pytest.raises(ShubException) as exc:
        _extract_metadata_from_image_info_output(json.dumps(output))
    assert error_msg in exc.value.message
