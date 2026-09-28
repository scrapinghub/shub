import os
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, mock

import pytest

from shub.exceptions import BadConfigException, BadParameterException, NotFoundException
from shub.image.utils import (
    STATUS_FILE_LOCATION,
    format_image_name,
    get_credentials,
    get_docker_client,
    get_image_registry,
    get_project_dir,
    load_status_url,
    store_status_url,
)

from .utils import FakeProjectDirectory, add_sh_fake_config


class ReleaseUtilsTest(TestCase):
    def test_get_project_dir(self):
        with pytest.raises(BadConfigException):
            get_project_dir()
        with FakeProjectDirectory() as tmpdir:
            add_sh_fake_config(tmpdir)
            assert get_project_dir() == tmpdir

    def test_get_docker_client(self):
        mocked_docker = mock.Mock()
        sys.modules["docker"] = mocked_docker
        client_mock = mock.Mock()

        class DockerClientMock:
            def __init__(self, *args, **kwargs):
                client_mock(*args, **kwargs)

            def version(self):
                return {}

        mocked_docker.APIClient = DockerClientMock
        assert get_docker_client()
        client_mock.assert_called_with(base_url=None, tls=None, version="auto")
        # set basic test environment
        os.environ["DOCKER_HOST"] = "http://127.0.0.1"
        os.environ["DOCKER_API_VERSION"] = "1.40"
        assert get_docker_client()
        client_mock.assert_called_with(
            base_url="http://127.0.0.1", tls=None, version="1.40"
        )
        # test for tls
        os.environ["DOCKER_TLS_VERIFY"] = "1"
        os.environ["DOCKER_CERT_PATH"] = "some-path"
        mocked_tls = mock.Mock()
        mocked_docker.tls.TLSConfig.return_value = mocked_tls
        assert get_docker_client()
        client_mock.assert_called_with(
            base_url="http://127.0.0.1", tls=mocked_tls, version="1.40"
        )
        mocked_docker.tls.TLSConfig.assert_called_with(
            client_cert=(
                str(Path("some-path", "cert.pem")),
                str(Path("some-path", "key.pem")),
            ),
            verify=str(Path("some-path", "ca.pem")),
            assert_hostname=False,
        )

    def test_format_image_name(self):
        assert format_image_name("simple", "tag") == "simple:tag"
        assert format_image_name("user/simple", "tag") == "user/simple:tag"
        assert (
            format_image_name("registry/user/simple", "tag")
            == "registry/user/simple:tag"
        )
        assert (
            format_image_name("registry:port/user/simple", "tag")
            == "registry:port/user/simple:tag"
        )
        assert (
            format_image_name("registry:port/user/simple:test", "tag")
            == "registry:port/user/simple:tag"
        )
        with mock.patch("shub.config.load_shub_config") as mocked:
            config = mock.Mock()
            config.get_version.return_value = "test-version"
            mocked.return_value = config
            assert format_image_name("test", None) == "test:test-version"

    def test_get_credentials(self):
        assert get_credentials(insecure=True) == (None, None)
        with pytest.raises(BadParameterException):
            get_credentials(username="user", insecure=True)
        with pytest.raises(BadParameterException):
            get_credentials(password="pass", insecure=True)
        assert get_credentials(apikey="apikey") == ("apikey", " ")
        assert get_credentials(username="user", password="pass") == ("user", "pass")
        with pytest.raises(BadParameterException):
            get_credentials(username="user")
        with pytest.raises(BadParameterException):
            get_credentials(password="pass")
        assert get_credentials(target_apikey="tapikey") == ("tapikey", " ")

    def test_get_image_registry(self):
        assert get_image_registry("ubuntu:12.04") is None
        assert get_image_registry("someuser/image:tagA") is None
        assert get_image_registry("registry.io/imageA") == "registry.io"
        assert get_image_registry("registry.io/user/name:tag") == "registry.io"
        assert get_image_registry("registry:8012/image") == "registry:8012"
        assert get_image_registry("registry:8012/user/repo") == "registry:8012"


class StatusUrlsTest(TestCase):
    def setUp(self):
        self.curdir = Path.cwd()
        self.tmp_dir = tempfile.gettempdir()
        os.chdir(self.tmp_dir)
        self.status_file = Path(self.tmp_dir, STATUS_FILE_LOCATION)
        self.status_file.unlink(missing_ok=True)

    def tearDown(self):
        os.chdir(self.curdir)

    def test_load_status_url(self):
        with pytest.raises(NotFoundException):
            load_status_url(0)
        # try with void file
        self.status_file.touch()
        with pytest.raises(BadConfigException):
            load_status_url(0)
        # try with data
        self.status_file.write_text("1: http://link1\n2: https://link2\n")
        with pytest.raises(NotFoundException):
            load_status_url(0)
        assert load_status_url(1) == "http://link1"
        assert load_status_url(2) == "https://link2"

    def test_store_status_url(self):
        assert not self.status_file.exists()
        # create and add first entry
        store_status_url("http://test0", 2)
        assert self.status_file.exists()
        assert self.status_file.read_text() == "0: http://test0\n"
        # add another one
        store_status_url("http://test1", 2)
        assert self.status_file.read_text() == "0: http://test0\n1: http://test1\n"
        # replacement
        assert store_status_url("http://test2", 2) == 2
        assert self.status_file.read_text() == "1: http://test1\n2: http://test2\n"
        # existing
        assert store_status_url("http://test1", 2) == 1
        assert self.status_file.read_text() == "1: http://test1\n2: http://test2\n"
