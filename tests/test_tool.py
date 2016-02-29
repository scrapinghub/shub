from click.testing import CliRunner
from unittest import TestCase
from kumo_release.tool import cli


class TestToolCli(TestCase):

    def test_cli(self):
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert 'Scrapinghub release tool' in result.output
        assert 'Options:' in result.output
        assert 'Commands:' in result.output
