import os
import mock
from click.testing import CliRunner
from unittest import TestCase
from kumo_release.upload import cli

from .utils import FakeProjectDirectory
from .utils import add_sh_fake_config

class TestUploadCli(TestCase):

    @mock.patch('kumo_release.deploy.deploy_cmd')
    @mock.patch('kumo_release.push.push_cmd')
    @mock.patch('kumo_release.build.build_cmd')
    def test_cli(self, build, push, deploy):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["dev", "-d", "--version", "test",
                  "--username", "user", "--password", "pass",
                  "--email", "mail", "--sync"])
        assert result.exit_code == 0
        build.assert_called_with('dev', True, 'test')
        push.assert_called_with('dev', True, 'test', 'user', 'pass', 'mail')
        deploy.assert_called_with('dev', True, 'test', 'user',
                                  'pass', 'mail', True)
