from unittest import mock, TestCase

from click.testing import CliRunner

from shub.image.upload import cli


class TestUploadCli(TestCase):

    @mock.patch('shub.image.deploy.deploy_cmd')
    @mock.patch('shub.image.push.push_cmd')
    @mock.patch('shub.image.build.build_cmd')
    def test_cli(self, build, push, deploy):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["dev", "-v", "--version", "test",
                  "--username", "user", "--password", "pass",
                  "--email", "mail", "--async", "--apikey", "apikey",
                  "--skip-tests", "--no-cache", "-f", "Dockerfile", "--reauth"])
        assert result.exit_code == 0
        build.assert_called_with('dev', 'test', True, True, (), filename='Dockerfile')
        push.assert_called_with(
            'dev', 'test', 'user', 'pass', 'mail', "apikey", False, reauth=True,
            skip_tests=True)
        deploy.assert_called_with(
            'dev', 'test', 'user', 'pass', 'mail', "apikey", False, True)

    @mock.patch('shub.image.upload.get_version', return_value='1565968870')
    @mock.patch('shub.image.deploy.deploy_cmd')
    @mock.patch('shub.image.push.push_cmd')
    @mock.patch('shub.image.build.build_cmd')
    def test_cli_default_version(self, build, push, deploy, get_version):
        result = CliRunner().invoke(cli, ["dev"])
        assert result.exit_code == 0
        get_version.assert_called_once_with()
        assert build.call_args[0][1] == '1565968870'
        assert push.call_args[0][1] == '1565968870'
        assert deploy.call_args[0][1] == '1565968870'
