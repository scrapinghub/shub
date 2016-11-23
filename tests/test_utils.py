import os
import sys
import tempfile
from six import StringIO
from unittest import TestCase

import mock
import click
import pytest
from shub import exceptions as shub_exceptions

from shub_image.utils import missing_modules
from shub_image.utils import get_project_dir
from shub_image.utils import get_docker_client
from shub_image.utils import format_image_name
from shub_image.utils import get_credentials

from shub_image.utils import ReleaseConfig
from shub_image.utils import load_release_config

from shub_image.utils import store_status_url
from shub_image.utils import load_status_url
from shub_image.utils import STATUS_FILE_LOCATION

from .utils import FakeProjectDirectory, add_sh_fake_config


class ReleaseUtilsTest(TestCase):

    def test_missing_modules(self):
        assert missing_modules() == []
        assert missing_modules('os', 'non-existing-module') == \
            ['non-existing-module']
        assert missing_modules('os', 'six', 'xxx11', 'xxx22') == \
            ['xxx11', 'xxx22']

    def test_get_project_dir(self):
        self.assertRaises(
            shub_exceptions.BadConfigException, get_project_dir)
        with FakeProjectDirectory() as tmpdir:
            add_sh_fake_config(tmpdir)
            assert get_project_dir() == tmpdir

    def test_get_docker_client(self):
        mocked_docker = mock.Mock()
        sys.modules['docker'] = mocked_docker
        client_mock = mock.Mock()

        class DockerClientMock(object):

            def __init__(self, *args, **kwargs):
                client_mock(*args, **kwargs)

            def version(self):
                return {}

        mocked_docker.Client = DockerClientMock
        assert get_docker_client()
        client_mock.assert_called_with(
            base_url=None, tls=None, version='1.17')
        # set basic test environment
        os.environ['DOCKER_HOST'] = 'http://127.0.0.1'
        os.environ['DOCKER_VERSION'] = '1.18'
        assert get_docker_client()
        client_mock.assert_called_with(
            base_url='http://127.0.0.1', tls=None, version='1.18')
        # test for tls
        os.environ['DOCKER_TLS_VERIFY'] = '1'
        os.environ['DOCKER_CERT_PATH'] = '/tmp/cert/path'
        mocked_tls = mock.Mock()
        mocked_docker.tls.TLSConfig.return_value = mocked_tls
        assert get_docker_client()
        client_mock.assert_called_with(
            base_url='http://127.0.0.1',
            tls=mocked_tls,
            version='1.18')
        mocked_docker.tls.TLSConfig.assert_called_with(
            client_cert=('/tmp/cert/path/cert.pem', '/tmp/cert/path/key.pem'),
            verify='/tmp/cert/path/ca.pem',
            assert_hostname=False)

    def test_format_image_name(self):
        assert format_image_name('simple', 'tag') == 'simple:tag'
        assert format_image_name('user/simple', 'tag') == 'user/simple:tag'
        assert format_image_name('registry/user/simple', 'tag') == \
            'registry/user/simple:tag'
        assert format_image_name('registry:port/user/simple', 'tag') == \
            'registry:port/user/simple:tag'
        assert format_image_name('registry:port/user/simple:test', 'tag') == \
            'registry:port/user/simple:tag'
        with mock.patch('shub.config.load_shub_config') as mocked:
            config = mock.Mock()
            config.get_version.return_value = 'test-version'
            mocked.return_value = config
            assert format_image_name('test', None) == 'test:test-version'

    def test_get_credentials(self):
        assert get_credentials(insecure=True) == (None, None)
        assert get_credentials(apikey='apikey') == ('apikey', ' ')
        assert get_credentials(
            username='user', password='pass') == ('user', 'pass')
        with pytest.raises(click.BadParameter):
            get_credentials(username='user')
        assert get_credentials(target_apikey='tapikey') == ('tapikey', ' ')


class ReleaseConfigTest(TestCase):

    def test_init(self):
        config = ReleaseConfig()
        assert hasattr(config, 'images')
        assert config.images == {}

    def test_load(self):
        config = ReleaseConfig()
        stream = StringIO(
            'projects:\n  dev: 123\n  prod: 321\n'
            'images:\n  dev: registry/user/project\n  prod: user/project\n'
            'endpoints:\n  dev: http://127.0.0.1/api/scrapyd/\n'
            'apikeys:\n  default: abcde\n'
            'version: GIT')
        config.load(stream)
        assert getattr(config, 'projects') == {'dev': 123, 'prod': 321}
        assert getattr(config, 'endpoints') == {
            'default': 'https://app.scrapinghub.com/api/',
            'dev': 'http://127.0.0.1/api/scrapyd/'}
        assert config.images == {
            'dev': 'registry/user/project',
            'prod': 'user/project'}
        assert getattr(config, 'apikeys') == {'default': 'abcde'}
        assert getattr(config, 'version') == 'GIT'

    def test_get_image(self):
        config = ReleaseConfig()
        config.images = {'dev': 'registry/user/project'}
        self.assertRaises(shub_exceptions.NotFoundException,
                          config.get_image, 'test')
        assert config.get_image('dev') == 'registry/user/project'

    def test_load_release_config(self):
        assert isinstance(load_release_config(), ReleaseConfig)


class StatusUrlsTest(TestCase):

    def setUp(self):
        tmpdir = tempfile.gettempdir()
        os.chdir(tmpdir)
        self.status_file = os.path.join(tmpdir, STATUS_FILE_LOCATION)
        if os.path.exists(self.status_file):
            os.remove(self.status_file)

    def test_load_status_url(self):
        self.assertRaises(shub_exceptions.NotFoundException,
                          load_status_url, 0)
        # try with void file
        open(self.status_file, 'a').close()
        self.assertRaises(shub_exceptions.BadConfigException,
                          load_status_url, 0)
        # try with data
        with open(self.status_file, 'w') as f:
            f.write('1: http://link1\n2: https://link2\n')
        self.assertRaises(shub_exceptions.NotFoundException,
                          load_status_url, 0)
        assert load_status_url(1) == 'http://link1'
        assert load_status_url(2) == 'https://link2'

    def test_store_status_url(self):
        assert not os.path.exists(self.status_file)
        # create and add first entry
        store_status_url('http://test0', 2)
        assert os.path.exists(self.status_file)
        with open(self.status_file, 'r') as f:
            assert f.read() == '0: http://test0\n'
        # add another one
        store_status_url('http://test1', 2)
        with open(self.status_file, 'r') as f:
            assert f.read() == '0: http://test0\n1: http://test1\n'
        # replacement
        assert store_status_url('http://test2', 2) == 2
        with open(self.status_file, 'r') as f:
            assert f.read() == '1: http://test1\n2: http://test2\n'
        # existing
        assert store_status_url('http://test1', 2) == 1
        with open(self.status_file, 'r') as f:
            assert f.read() == '1: http://test1\n2: http://test2\n'
