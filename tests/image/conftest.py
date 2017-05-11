# -*- coding: utf-8 -*-
import inspect
from functools import wraps

import mock
import pytest

from shub.image.utils import ProgressBar

from .utils import (
    FakeProjectDirectory, add_scrapy_fake_config, add_sh_fake_config,
    add_fake_dockerfile, add_fake_setup_py,
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
        add_fake_setup_py(tmpdir)
        yield tmpdir


@pytest.fixture
def monkeypatch_bar_rate(monkeypatch):
    args, _, _, _ = inspect.getargspec(ProgressBar.format_meter)
    rate_arg_idx = args.index('rate')

    def override_rate(func):

        @wraps(func)
        def wrapper(*args, **kwargs):
            args = list(args)
            args[rate_arg_idx] = 10 ** 6
            return func(*args, **kwargs)

        return wrapper

    monkeypatch.setattr('shub.image.utils.ProgressBar.format_meter',
                        staticmethod(override_rate(ProgressBar.format_meter)))
