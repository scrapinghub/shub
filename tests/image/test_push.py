# -*- coding: utf-8 -*-
import re
import mock
import pytest
from click.testing import CliRunner
from shub import exceptions as shub_exceptions
from shub.image.push import cli
from ..utils import format_expected_progress


@pytest.fixture
def test_mock():
    """Mock for shub image test command"""
    with mock.patch('shub.image.push.test_cmd') as m:
        yield m


@pytest.mark.usefixtures('project_dir')
def test_cli_with_apikey_login(docker_client_mock, test_mock):
    docker_client_mock.login.return_value = {"Status": "Login Succeeded"}
    docker_client_mock.push.return_value = [
        {"stream": "In process"},
        {"status": "Successfully pushed"}
    ]
    runner = CliRunner()
    result = runner.invoke(cli, ["dev", "--version", "test"])
    assert result.exit_code == 0
    docker_client_mock.push.assert_called_with(
        'registry/user/project:test', decode=True,
        insecure_registry=False, stream=True)
    test_mock.assert_called_with("dev", "test")


@pytest.mark.usefixtures('project_dir')
def test_cli_with_progress(docker_client_mock, test_mock):
    docker_client_mock.login.return_value = {"Status": "Login Succeeded"}
    docker_client_mock.push.return_value = [
        {"status": "The push refers to a repository [some/image]"},
        {"status": "Preparing", "progressDetail": {}, "id": "abc"},
        {"status": "Preparing", "progressDetail": {}, "id": "def"},
        {"status": "Preparing", "progressDetail": {}, "id": "egh"},
        {"status": "Waiting", "progressDetail": {}, "id": "abc"},
        {"status": "Waiting", "progressDetail": {}, "id": "egh"},
        {"status": "Pushing", "progressDetail": {"current": 512, "total": 24803}, "id": "abc"},
        {"status": "Layer already exists", "progressDetail": {}, "id": "def"},
        {"status": "Pushing", "progressDetail": {"current": 57344, "total": 26348}, "id": "egh"},
        {"status": "Pushed", "progressDetail": {}, "id": "egh"},
        {"status": "Pushing", "progressDetail": {"current": 24805, "total": 24803}, "id": "abc"},
        {"status": "Pushed", "progressDetail": {}, "id": "abc"},
        {"status": "Successfully pushed"}
    ]
    runner = CliRunner()
    result = runner.invoke(cli, ["dev", "--version", "test"])
    assert result.exit_code == 0
    assert result.output.startswith(
        'Login to registry succeeded.\n'
        'Pushing registry/user/project:test to the registry.\n\r'
    )
    # the following string is regexp because push tqdm speed estimation
    # depends on time and always different
    expected = format_expected_progress(
        'Layers:  33%\|███▎      \| 1/3\r          \r'
        'Layers:  67%\|██████▋   \| 2/3\r'
        'Layers: 100%\|██████████\| 3/3\n\r'
        'abc: 100%\|██████████\| 24.8K/24.8K \[[?.0-9]*[KM]?B/s\]\n\r'
        'egh: 100%\|██████████\| 26.3K/26.3K \[[?.0-9]*[KM]?B/s\]\n'
        'The image registry/user/project:test pushed successfully\.\n'
    )
    matched = re.search(expected, result.output)
    assert matched
    # to make sure the test regexp below is correct
    assert matched.group(0).startswith('Layers:  33%')
    assert matched.group(0).endswith('pushed successfully.\n')


@pytest.mark.usefixtures('project_dir')
def test_cli_with_custom_login(docker_client_mock, test_mock):
    docker_client_mock.login.return_value = {"Status": "Login Succeeded"}
    docker_client_mock.push.return_value = [
        {"stream": "In process"},
        {"status": "Successfully pushed"}
    ]
    runner = CliRunner()
    result = runner.invoke(
        cli, ["dev", "--version", "test", "--username", "user",
              "--password", "pass", "--email", "mail"])
    assert result.exit_code == 0
    docker_client_mock.login.assert_called_with(
        email=u'mail', password=u'pass',
        reauth=False, registry='registry', username=u'user')
    docker_client_mock.push.assert_called_with(
        'registry/user/project:test', decode=True,
        insecure_registry=False, stream=True)
    test_mock.assert_called_with("dev", "test")


@pytest.mark.usefixtures('project_dir')
def test_cli_with_insecure_registry(docker_client_mock, test_mock):
    docker_client_mock.login.return_value = {"Status": "Login Succeeded"}
    docker_client_mock.push.return_value = [
        {"stream": "In process"},
        {"status": "Successfully pushed"}
    ]
    runner = CliRunner()
    result = runner.invoke(
        cli, ["dev", "--version", "test", "--insecure"])
    assert result.exit_code == 0
    assert not docker_client_mock.login.called
    docker_client_mock.push.assert_called_with(
        'registry/user/project:test', decode=True,
        insecure_registry=True, stream=True)
    test_mock.assert_called_with("dev", "test")


@pytest.mark.usefixtures('project_dir')
def test_cli_with_login_username_only(docker_client_mock, test_mock):
    docker_client_mock.login.return_value = {"Status": "Login Succeeded"}
    docker_client_mock.push.return_value = [
        {"stream": "In process"},
        {"status": "Successfully pushed"}
    ]
    runner = CliRunner()
    result = runner.invoke(
        cli, ["dev", "--version", "test", "--apikey", "apikey"])
    assert result.exit_code == 0
    docker_client_mock.login.assert_called_with(
        email=None, password=' ',
        reauth=False, registry='registry', username='apikey')
    docker_client_mock.push.assert_called_with(
        'registry/user/project:test', decode=True,
        insecure_registry=False, stream=True)
    test_mock.assert_called_with("dev", "test")


@pytest.mark.usefixtures('project_dir')
def test_cli_login_fail(docker_client_mock, test_mock):
    docker_client_mock.login.return_value = {"Status": "Login Failed!"}
    runner = CliRunner()
    result = runner.invoke(
        cli, ["dev", "--version", "test", "--username", "user",
              "--password", "pass", "--email", "mail"])
    assert result.exit_code == shub_exceptions.RemoteErrorException.exit_code
    test_mock.assert_called_with("dev", "test")


@pytest.mark.usefixtures('project_dir')
def test_cli_push_fail(docker_client_mock, test_mock):
    docker_client_mock.login.return_value = {"Status": "Login Succeeded"}
    docker_client_mock.push.return_value = [{"error": "Failed:(", "errorDetail": ""}]
    runner = CliRunner()
    result = runner.invoke(
        cli, ["dev", "--version", "test", "--username", "user",
              "--password", "pass", "--email", "mail"])
    assert result.exit_code == shub_exceptions.RemoteErrorException.exit_code
    test_mock.assert_called_with("dev", "test")


@pytest.mark.usefixtures('project_dir')
@pytest.mark.parametrize('skip_tests_flag', ['-S', '--skip-tests'])
def test_cli_skip_tests(docker_client_mock, test_mock, skip_tests_flag):
    docker_client_mock.login.return_value = {"Status": "Login Succeeded"}
    docker_client_mock.push.return_value = [
        {"stream": "In process"},
        {"status": "Successfully pushed"}
    ]
    runner = CliRunner()
    result = runner.invoke(cli, ["dev", "--version", "test", skip_tests_flag])
    assert result.exit_code == 0
    docker_client_mock.push.assert_called_with(
        'registry/user/project:test', decode=True,
        insecure_registry=False, stream=True)
    assert test_mock.call_count == 0
