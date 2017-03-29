# -*- coding: utf-8 -*-
import mock
import pytest


@pytest.fixture
def docker_client_mock():
    client_mock = mock.Mock()
    with mock.patch('shub.image.utils.get_docker_client') as m:
        m.return_value = client_mock
        yield client_mock


@pytest.fixture
def test_mock():
    with mock.patch('shub.image.test.test_cmd') as m:
        yield m
