import os

import pytest
from click.testing import CliRunner
from shub import exceptions as shub_exceptions
from shub.image.build import cli


def test_cli(docker_client_mock, project_dir, test_mock):
    docker_client_mock.build.return_value = [
        {"stream": "all is ok"},
        {"stream": "Successfully built 12345"}
    ]
    setup_py_path = os.path.join(project_dir, 'setup.py')
    assert not os.path.isfile(setup_py_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["dev", "-v"])
    assert result.exit_code == 0
    docker_client_mock.build.assert_called_with(
        decode=True, path=project_dir, tag='registry/user/project:1.0')
    assert os.path.isfile(setup_py_path)
    test_mock.assert_called_with("dev", None)


def test_cli_custom_version(docker_client_mock, project_dir, test_mock):
    docker_client_mock.build.return_value = [
        {"stream": "all is ok"},
        {"stream": "Successfully built 12345"}
    ]
    runner = CliRunner()
    result = runner.invoke(cli, ["dev", "--version", "test"])
    assert result.exit_code == 0
    docker_client_mock.build.assert_called_with(
        decode=True, path=project_dir, tag='registry/user/project:test')
    test_mock.assert_called_with("dev", "test")


def test_cli_no_dockerfile(docker_client_mock, project_dir):
    docker_client_mock.build.return_value = [
        {"error": "Minor", "errorDetail": "Testing output"},
        {"stream": "Successfully built 12345"}
    ]
    os.remove(os.path.join(project_dir, 'Dockerfile'))
    runner = CliRunner()
    result = runner.invoke(cli, ["dev"])
    assert result.exit_code == shub_exceptions.BadParameterException.exit_code

@pytest.mark.usefixtures('project_dir')
def test_cli_fail(docker_client_mock):
    docker_client_mock.build.return_value = [
        {"error": "Minor", "errorDetail": "Test"}
    ]
    runner = CliRunner()
    result = runner.invoke(cli, ["dev"])
    assert result.exit_code == shub_exceptions.RemoteErrorException.exit_code


@pytest.mark.parametrize('skip_tests_flag', ['-S', '--skip-tests'])
def test_cli_skip_tests(docker_client_mock, test_mock, project_dir, skip_tests_flag):
    docker_client_mock.build.return_value = [
        {"stream": "all is ok"},
        {"stream": "Successfully built 12345"}
    ]
    setup_py_path = os.path.join(project_dir, 'setup.py')
    assert not os.path.isfile(setup_py_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["dev", skip_tests_flag])
    assert result.exit_code == 0
    docker_client_mock.build.assert_called_with(
        decode=True, path=project_dir, tag='registry/user/project:1.0')
    assert os.path.isfile(setup_py_path)
    assert test_mock.call_count == 0
