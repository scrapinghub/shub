import mock
from click.testing import CliRunner

from shub.image.deploy import cli
from shub.image.deploy import _prepare_deploy_params
from shub.image.deploy import _extract_scripts_from_project

from .utils import FakeProjectDirectory
from .utils import add_sh_fake_config
from .utils import add_fake_setup_py
from .utils import add_scrapy_fake_config


@mock.patch('requests.get')
@mock.patch('requests.post')
@mock.patch('shub.image.list.list_cmd')
def test_cli(list_mocked, post_mocked, get_mocked):
    list_mocked.return_value = ['a1f', 'abc', 'spi-der']
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
        auth_cfg = '{"email": null, "password": " ", "username": "abcdef"}'
        post_mocked.assert_called_with(
            'https://app.scrapinghub.com/api/releases/deploy.json',
            allow_redirects=False, auth=('abcdef', ''),
            data={'project': 12345,
                    'version': u'test',
                    'pull_auth_config': auth_cfg,
                    'image_url': 'registry/user/project:test',
                    'spiders': 'a1f,abc,spi-der',
                    'scripts': 'scriptA.py,scriptB.py'}, timeout=300)
        get_mocked.assert_called_with('https://status-url', timeout=300)


@mock.patch('requests.get')
@mock.patch('requests.post')
@mock.patch('shub.image.list.list_cmd')
def test_cli_insecure_registry(list_mocked, post_mocked, get_mocked):
    list_mocked.return_value = ['a1f', 'abc', 'spi-der']
    post_req = mock.Mock()
    post_req.headers = {'location': 'https://status-url'}
    post_mocked.return_value = post_req

    with FakeProjectDirectory() as tmpdir:
        add_scrapy_fake_config(tmpdir)
        add_sh_fake_config(tmpdir)
        add_fake_setup_py(tmpdir)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["dev", "--version", "test", "--insecure"])
        assert result.exit_code == 0
        post_mocked.assert_called_with(
            'https://app.scrapinghub.com/api/releases/deploy.json',
            allow_redirects=False, auth=('abcdef', ''),
            data={'project': 12345,
                    'version': u'test',
                    'pull_insecure_registry': True,
                    'image_url': 'registry/user/project:test',
                    'spiders': 'a1f,abc,spi-der',
                    'scripts': 'scriptA.py,scriptB.py'}, timeout=300)
        get_mocked.assert_called_with('https://status-url', timeout=300)


# Tests for auxiliary functions

def test_extract_scripts_from_project():
    assert _extract_scripts_from_project() == ''
    with FakeProjectDirectory() as tmpdir:
        add_fake_setup_py(tmpdir)
        assert _extract_scripts_from_project() == 'scriptA.py,scriptB.py'


@mock.patch('shub.image.list.list_cmd')
def test_prepare_deploy_params(mocked):
    mocked.return_value = ['a1f', 'abc', 'spi-der']
    with FakeProjectDirectory() as tmpdir:
        add_fake_setup_py(tmpdir)
        assert _prepare_deploy_params(
            123, 'test-vers', 'registry/user/project',
            'endpoint', 'apikey', None, None, None) == {
                'image_url': 'registry/user/project',
                'project': 123,
                'pull_insecure_registry': True,
                'scripts': 'scriptA.py,scriptB.py',
                'spiders': 'a1f,abc,spi-der',
                'version': 'test-vers'}


@mock.patch('shub.image.list.list_cmd')
def test_prepare_deploy_params_more_params(mocked):
    mocked.return_value = ['a1f', 'abc', 'spi-der']
    with FakeProjectDirectory() as tmpdir:
        add_fake_setup_py(tmpdir)
        expected_auth = ('{"email": "email@mail", "password":'
                            ' "pass", "username": "user"}')
        assert _prepare_deploy_params(
            123, 'test-vers', 'registry/user/project',
            'endpoint', 'apikey', 'user', 'pass', 'email@mail') == {
                'image_url': 'registry/user/project',
                'project': 123,
                'pull_auth_config': expected_auth,
                'scripts': 'scriptA.py,scriptB.py',
                'spiders': 'a1f,abc,spi-der',
                'version': 'test-vers'}
