import runpy
import sys
from unittest import mock

import pytest


@pytest.mark.parametrize('argv0', [
    '/usr/local/bin/shub',
    '/usr/lib/python3/shub/__main__.py',
])
def test_prog_name(argv0, monkeypatch):
    monkeypatch.setattr(sys, 'argv', [argv0])

    with mock.patch('shub.tool.cli') as cli:
        runpy.run_module('shub.__main__', run_name='__main__')

    assert cli.call_args == mock.call(prog_name='shub')
