import os
import mock
from click.testing import CliRunner
from unittest import TestCase
from shub import exceptions as shub_exceptions
from shub.image.build import cli

from .utils import FakeProjectDirectory
from .utils import add_sh_fake_config
from .utils import add_fake_dockerfile
from .utils import add_scrapy_fake_config


@mock.patch('shub.image.utils.get_docker_client')
class TestBuildCli(TestCase):

    @mock.patch('shub.image.test.test_cmd')
    def test_cli(self, test_mock, mocked_method):
        mocked = mock.MagicMock()
        mocked.build.return_value = [
            {"stream": "all is ok"},
            {"stream": "Successfully built 12345"}]
        mocked_method.return_value = mocked
        with FakeProjectDirectory() as tmpdir:
            add_scrapy_fake_config(tmpdir)
            add_sh_fake_config(tmpdir)
            add_fake_dockerfile(tmpdir)
            setup_py_path = os.path.join(tmpdir, 'setup.py')
            assert not os.path.isfile(setup_py_path)
            runner = CliRunner()
            result = runner.invoke(cli, ["dev", "-d"])
            assert result.exit_code == 0
            mocked.build.assert_called_with(
                decode=True, path=tmpdir, tag='registry/user/project:1.0')
            assert os.path.isfile(setup_py_path)
            test_mock.assert_called_with("dev", None)

    @mock.patch('shub.image.test.test_cmd')
    def test_cli_custom_version(self, test_mock, mocked_method):
        mocked = mock.MagicMock()
        mocked.build.return_value = [
            {"stream": "all is ok"},
            {"stream": "Successfully built 12345"}]
        mocked_method.return_value = mocked
        with FakeProjectDirectory() as tmpdir:
            add_scrapy_fake_config(tmpdir)
            add_sh_fake_config(tmpdir)
            add_fake_dockerfile(tmpdir)
            runner = CliRunner()
            result = runner.invoke(cli, ["dev", "--version", "test"])
            assert result.exit_code == 0
            mocked.build.assert_called_with(
                decode=True, path=tmpdir, tag='registry/user/project:test')
            test_mock.assert_called_with("dev", "test")

    def test_cli_no_dockerfile(self, mocked_method):
        mocked = mock.MagicMock()
        mocked.build.return_value = [
            {"error": "Minor", "errorDetail": "Testing output"},
            {"stream": "Successfully built 12345"}]
        mocked_method.return_value = mocked
        with FakeProjectDirectory() as tmpdir:
            add_scrapy_fake_config(tmpdir)
            add_sh_fake_config(tmpdir)
            runner = CliRunner()
            result = runner.invoke(cli, ["dev"])
            assert result.exit_code == \
                shub_exceptions.BadParameterException.exit_code

    def test_cli_fail(self, mocked_method):
        mocked = mock.MagicMock()
        mocked.build.return_value = [{"error": "Minor", "errorDetail": "Test"}]
        mocked_method.return_value = mocked
        with FakeProjectDirectory() as tmpdir:
            add_scrapy_fake_config(tmpdir)
            add_sh_fake_config(tmpdir)
            add_fake_dockerfile(tmpdir)
            runner = CliRunner()
            result = runner.invoke(cli, ["dev"])
            assert result.exit_code == \
                shub_exceptions.RemoteErrorException.exit_code
