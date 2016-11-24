from click.testing import CliRunner
from unittest import TestCase
from shub.image import image_cli


class TestToolCli(TestCase):

    def test_cli(self):
        runner = CliRunner()
        result = runner.invoke(image_cli, [])
        assert result.exit_code == 0
        assert 'Release project with Docker' in result.output
        assert 'Options:' in result.output
        assert 'Commands:' in result.output
