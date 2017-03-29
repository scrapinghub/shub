import os

from click.testing import CliRunner
from shub import exceptions as shub_exceptions
from shub.image.build import cli

from .utils import FakeProjectDirectory
from .utils import add_sh_fake_config
from .utils import add_fake_dockerfile
from .utils import add_scrapy_fake_config


def test_cli(docker_client_mock, test_mock):
    docker_client_mock.build.return_value = [
        {"stream": "all is ok"},
        {"stream": "Successfully built 12345"}
    ]
    with FakeProjectDirectory() as tmpdir:
        add_scrapy_fake_config(tmpdir)
        add_sh_fake_config(tmpdir)
        add_fake_dockerfile(tmpdir)
        setup_py_path = os.path.join(tmpdir, 'setup.py')
        assert not os.path.isfile(setup_py_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["dev", "-v"])
        assert result.exit_code == 0
        docker_client_mock.build.assert_called_with(
            decode=True, path=tmpdir, tag='registry/user/project:1.0')
        assert os.path.isfile(setup_py_path)
    test_mock.assert_called_with("dev", None)


def test_cli_custom_version(docker_client_mock, test_mock):
    docker_client_mock.build.return_value = [
        {"stream": "all is ok"},
        {"stream": "Successfully built 12345"}]
    with FakeProjectDirectory() as tmpdir:
        add_scrapy_fake_config(tmpdir)
        add_sh_fake_config(tmpdir)
        add_fake_dockerfile(tmpdir)
        runner = CliRunner()
        result = runner.invoke(cli, ["dev", "--version", "test"])
        assert result.exit_code == 0
        docker_client_mock.build.assert_called_with(
            decode=True, path=tmpdir, tag='registry/user/project:test')
    test_mock.assert_called_with("dev", "test")


def test_cli_no_dockerfile(docker_client_mock):
    docker_client_mock.build.return_value = [
        {"error": "Minor", "errorDetail": "Testing output"},
        {"stream": "Successfully built 12345"}]
    with FakeProjectDirectory() as tmpdir:
        add_scrapy_fake_config(tmpdir)
        add_sh_fake_config(tmpdir)
        runner = CliRunner()
        result = runner.invoke(cli, ["dev"])
        assert result.exit_code == \
            shub_exceptions.BadParameterException.exit_code


def test_cli_fail(docker_client_mock):
    docker_client_mock.build.return_value = [
        {"error": "Minor", "errorDetail": "Test"}
    ]
    with FakeProjectDirectory() as tmpdir:
        add_scrapy_fake_config(tmpdir)
        add_sh_fake_config(tmpdir)
        add_fake_dockerfile(tmpdir)
        runner = CliRunner()
        result = runner.invoke(cli, ["dev"])
        assert result.exit_code == \
            shub_exceptions.RemoteErrorException.exit_code
