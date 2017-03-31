# -*- coding: utf-8 -*-
import mock
import pytest

from .utils import (
    FakeProjectDirectory, add_scrapy_fake_config, add_sh_fake_config,
    add_fake_dockerfile
)

@pytest.fixture
def docker_client_mock():
    """Docker client mock"""
    client_mock = mock.Mock()
    with mock.patch('shub.image.utils.get_docker_client') as m:
        m.return_value = client_mock
        yield client_mock


@pytest.fixture
def project_dir():
    """Fake project directory"""
    with FakeProjectDirectory() as tmpdir:
        add_scrapy_fake_config(tmpdir)
        add_sh_fake_config(tmpdir)
        add_fake_dockerfile(tmpdir)
        yield tmpdir
