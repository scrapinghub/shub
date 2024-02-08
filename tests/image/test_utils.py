import os
import shutil
import sys
import tempfile
from unittest import mock, TestCase

import pytest

from shub.exceptions import BadConfigException, BadParameterException, NotFoundException
from shub.image.utils import (
    get_credentials,
    get_docker_client,
    get_image_registry,
    get_project_dir,
    format_image_name,
    load_status_url,
    store_status_url,
    STATUS_FILE_LOCATION,
    DEFAULT_DOCKER_API_VERSION,
)

from .utils import FakeProjectDirectory, add_sh_fake_config


class ReleaseUtilsTest(TestCase):

    def test_get_project_dir(self):
        self.assertRaises(BadConfigException, get_project_dir)
        with FakeProjectDirectory() as tmpdir:
            add_sh_fake_config(tmpdir)
            assert get_project_dir() == tmpdir

    def test_get_docker_client(self):
        mocked_docker = mock.Mock()
        sys.modules['docker'] = mocked_docker
        client_mock = mock.Mock()

        class DockerClientMock:

            def __init__(self, *args, **kwargs):
                client_mock(*args, **kwargs)

            def version(self):
                return {}

        mocked_docker.APIClient = DockerClientMock
        assert get_docker_client()
        client_mock.assert_called_with(
            base_url=None, tls=None, version=DEFAULT_DOCKER_API_VERSION)
        # set basic test environment
        os.environ['DOCKER_HOST'] = 'http://127.0.0.1'
        os.environ['DOCKER_API_VERSION'] = '1.40'
        assert get_docker_client()
        client_mock.assert_called_with(
            base_url='http://127.0.0.1', tls=None, version='1.40')
        # test for tls
        os.environ['DOCKER_TLS_VERIFY'] = '1'
        os.environ['DOCKER_CERT_PATH'] = 'some-path'
        mocked_tls = mock.Mock()
        mocked_docker.tls.TLSConfig.return_value = mocked_tls
        assert get_docker_client()
        client_mock.assert_called_with(
            base_url='http://127.0.0.1',
            tls=mocked_tls,
            version='1.40')
        mocked_docker.tls.TLSConfig.assert_called_with(
            client_cert=(os.path.join('some-path', 'cert.pem'),
                         os.path.join('some-path', 'key.pem')),
            verify=os.path.join('some-path', 'ca.pem'),
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
        with pytest.raises(BadParameterException):
            get_credentials(username='user', insecure=True)
        with pytest.raises(BadParameterException):
            get_credentials(password='pass', insecure=True)
        assert get_credentials(apikey='apikey') == ('apikey', ' ')
        assert get_credentials(
            username='user', password='pass') == ('user', 'pass')
        with pytest.raises(BadParameterException):
            get_credentials(username='user')
        with pytest.raises(BadParameterException):
            get_credentials(password='pass')
        assert get_credentials(target_apikey='tapikey') == ('tapikey', ' ')

    def test_get_image_registry(self):
        assert get_image_registry('ubuntu:12.04') is None
        assert get_image_registry('someuser/image:tagA') is None
        assert get_image_registry('registry.io/imageA') == 'registry.io'
        assert get_image_registry('registry.io/user/name:tag') == 'registry.io'
        assert get_image_registry('registry:8012/image') == 'registry:8012'
        assert get_image_registry('registry:8012/user/repo') == 'registry:8012'


class StatusUrlsTest(TestCase):

    def setUp(self):
        self.curdir = os.getcwd()
        self.tmp_dir = tempfile.gettempdir()
        os.chdir(self.tmp_dir)
        self.status_file = os.path.join(self.tmp_dir, STATUS_FILE_LOCATION)
        if os.path.exists(self.status_file):
            os.remove(self.status_file)

    def tearDown(self):
        os.chdir(self.curdir)

    def test_load_status_url(self):
        self.assertRaises(NotFoundException, load_status_url, 0)
        # try with void file
        open(self.status_file, 'a').close()
        self.assertRaises(BadConfigException, load_status_url, 0)
        # try with data
        with open(self.status_file, 'w') as f:
            f.write('1: http://link1\n2: https://link2\n')
        self.assertRaises(NotFoundException, load_status_url, 0)
        assert load_status_url(1) == 'http://link1'
        assert load_status_url(2) == 'https://link2'

    def test_store_status_url(self):
        assert not os.path.exists(self.status_file)
        # create and add first entry
        store_status_url('http://test0', 2)
        assert os.path.exists(self.status_file)
        with open(self.status_file) as f:
            assert f.read() == '0: http://test0\n'
        # add another one
        store_status_url('http://test1', 2)
        with open(self.status_file) as f:
            assert f.read() == '0: http://test0\n1: http://test1\n'
        # replacement
        assert store_status_url('http://test2', 2) == 2
        with open(self.status_file) as f:
            assert f.read() == '1: http://test1\n2: http://test2\n'
        # existing
        assert store_status_url('http://test1', 2) == 1
        with open(self.status_file) as f:
            assert f.read() == '1: http://test1\n2: http://test2\n'
