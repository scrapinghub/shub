import mock
from click.testing import CliRunner
from unittest import TestCase
from shub.image.upload import cli


class TestUploadCli(TestCase):

    @mock.patch('shub.image.deploy.deploy_cmd')
    @mock.patch('shub.image.push.push_cmd')
    @mock.patch('shub.image.build.build_cmd')
    def test_cli(self, build, push, deploy):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["dev", "-d", "--version", "test",
                  "--username", "user", "--password", "pass",
                  "--email", "mail", "--async", "--apikey", "apikey"])
        assert result.exit_code == 0
        build.assert_called_with('dev', 'test')
        push.assert_called_with(
            'dev', 'test', 'user', 'pass', 'mail', "apikey", False)
        deploy.assert_called_with(
            'dev', 'test', 'user', 'pass', 'mail', "apikey", False, True)
