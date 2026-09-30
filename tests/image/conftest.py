import os
from functools import wraps
from unittest import mock

import pytest

from shub.image.utils import ProgressBar

try:
    # https://stackoverflow.com/a/55000090
    from inspect import getfullargspec as get_args
except ImportError:
    from inspect import getargspec as get_args

from .utils import (
    SH_CONFIG_FILE, FakeProjectDirectory, add_scrapy_fake_config, add_sh_fake_config,
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
def logged_out(project_dir, monkeypatch):
    """Remove every API key source from the fake project directory"""
    with open(os.path.join(project_dir, 'scrapinghub.yml'), 'w') as f:
        f.write(SH_CONFIG_FILE.split('apikeys:')[0])
    monkeypatch.setattr('shub.config.GLOBAL_SCRAPINGHUB_YML_PATH',
                        os.path.join(project_dir, 'global.yml'))
    monkeypatch.setattr('shub.config.NETRC_PATH',
                        os.path.join(project_dir, 'netrc'))
    monkeypatch.delenv('SHUB_APIKEY', raising=False)


@pytest.fixture
def monkeypatch_bar_rate(monkeypatch):
    # Converting to List instead to unpacking the Tuple
    # because get_args returns different tuple sizes between py versions.
    args = list(get_args(ProgressBar.format_meter))[0]
    rate_arg_idx = args.index('rate')

    def override_rate(func):

        @wraps(func)
        def wrapper(*args, **kwargs):
            args = list(args)
            if 'rate' in args:
                args[rate_arg_idx] = 10 ** 6
            elif 'rate' in kwargs:
                kwargs['rate'] = 10 ** 6
            return func(*args, **kwargs)

        return wrapper

    monkeypatch.setattr('shub.image.utils.ProgressBar.format_meter',
                        staticmethod(override_rate(ProgressBar.format_meter)))
