import mock
from click.testing import CliRunner
from unittest import TestCase
from shub import exceptions as shub_exceptions
from shub_image.check import cli
from shub_image import utils


class TestCheckCli(TestCase):

    @mock.patch('requests.get')
    def test_cli(self, mocked):
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == \
            shub_exceptions.NotFoundException.exit_code
        deploy_id1 = utils.store_status_url('http://linkA', 2)
        deploy_id2 = utils.store_status_url('http://linkB', 2)
        utils.store_status_url('http://linkC', 2)

        # get latest (deploy 3)
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        mocked.assert_called_with('http://linkC', timeout=300)

        # get deploy by id
        result = runner.invoke(cli, ["--id", deploy_id2])
        assert result.exit_code == 0
        mocked.assert_called_with('http://linkB', timeout=300)

        # get non-existing deploy
        result = runner.invoke(cli, ["--id", deploy_id1])
        assert result.exit_code == \
            shub_exceptions.NotFoundException.exit_code
