import mock
import pytest
from click.testing import CliRunner
from shub import exceptions as shub_exceptions
from shub.image.push import cli


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
