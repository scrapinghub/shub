import os
import mock
from click.testing import CliRunner
from unittest import TestCase
from subprocess import CalledProcessError

from kumo_release.deploy import cli
from kumo_release.deploy import _prepare_deploy_params
from kumo_release.deploy import _extract_spiders_from_project
from kumo_release.deploy import _extract_scripts_from_project

from .utils import FakeProjectDirectory
from .utils import add_sh_fake_config
from .utils import add_fake_setup_py
from .utils import add_scrapy_fake_config

class TestDeployCli(TestCase):

    @mock.patch('requests.get')
    @mock.patch('requests.post')
    @mock.patch('subprocess.check_output')
    def test_cli(self, subp_mocked, post_mocked, get_mocked):
        subp_mocked.return_value = 'abc\na1f\njust row\nSome text\nspi-der'
        post_req = mock.Mock()
        post_req.headers = {'location': 'https://status-url'}
        post_mocked.return_value = post_req

        with FakeProjectDirectory() as tmpdir:
            add_scrapy_fake_config(tmpdir)
            add_sh_fake_config(tmpdir)
            add_fake_setup_py(tmpdir)

            runner = CliRunner()
            result = runner.invoke(cli, ["dev", "--version", "test"])
            assert result.exit_code == 0
            post_mocked.assert_called_with(
                'https://dash.scrapinghub.com/api/releases/deploy.json',
                allow_redirects=False, auth=('abcdef', ''),
                data={'project': 12345, 'pull_insecure_registry': True,
                      'version': u'test',
                      'image_url': 'registry/user/project:test',
                      'spiders': 'a1f,abc,spi-der',
                      'scripts': 'scriptA.py,scriptB.py'}, timeout=300)
            get_mocked.assert_called_with('https://status-url', timeout=300)


class TestDeployTools(TestCase):

    @mock.patch('subprocess.check_output')
    def test_extract_spiders_from_project(self, mocked):
        mocked.return_value = 'abc\na1f\njust row\nSome text\nspi-der'
        assert _extract_spiders_from_project() == 'a1f,abc,spi-der'
        mocked.side_effect = CalledProcessError(-1, ['scrapy', 'list'])
        assert _extract_spiders_from_project() == ''

    def test_extract_scripts_from_project(self):
        assert _extract_scripts_from_project() == ''
        with FakeProjectDirectory() as tmpdir:
            add_fake_setup_py(tmpdir)
            assert _extract_scripts_from_project() == 'scriptA.py,scriptB.py'

    @mock.patch('subprocess.check_output')
    def test_prepare_deploy_params(self, mocked):
        mocked.return_value = 'abc\na1f\njust row\nSome text\nspi-der'
        with FakeProjectDirectory() as tmpdir:
            add_fake_setup_py(tmpdir)
            assert _prepare_deploy_params(
                123, 'test-vers', 'registry/user/project',
                None, None, None, False) == {
                    'image_url': 'registry/user/project',
                    'project': 123,
                    'pull_insecure_registry': True,
                    'scripts': 'scriptA.py,scriptB.py',
                    'spiders': 'a1f,abc,spi-der',
                    'version': 'test-vers'}

    @mock.patch('subprocess.check_output')
    def test_prepare_deploy_params_more_params(self, mocked):
        mocked.return_value = 'abc\na1f\njust row\nSome text\nspi-der'
        with FakeProjectDirectory() as tmpdir:
            add_fake_setup_py(tmpdir)
            expected_auth = ('{"email": "email@mail", "password":'
                             ' "pass", "username": "user"}')
            assert _prepare_deploy_params(
                123, 'test-vers', 'registry/user/project',
                'user', 'pass', 'email@mail', True) == {
                    'image_url': 'registry/user/project',
                    'project': 123,
                    'pull_auth_config': expected_auth,
                    'sync': True,
                    'scripts': 'scriptA.py,scriptB.py',
                    'spiders': 'a1f,abc,spi-der',
                    'version': 'test-vers'}
