import sys
import re
from unittest import mock

from click.testing import CliRunner
from tqdm.utils import _supports_unicode

from shub import config


class AssertInvokeRaisesMixin:
    def assertInvokeRaises(self, exc, *args, **kwargs):
        """
        Invoke self.runner (or a new runner if nonexistent) with given *args
        and **kwargs, assert that it raised an exception of type exc, and
        return the runner's result.
        """
        runner = getattr(self, 'runner', None) or CliRunner()
        kwargs['standalone_mode'] = False
        result = runner.invoke(*args, **kwargs)
        self.assertIsInstance(result.exception, exc)
        return result


def mock_conf(testcase, target=None, attr=None, conf=None):
    if not conf:
        conf = config.ShubConfig()
        conf.projects.update({
            'default': 1,
            'prod': 2,
            'vagrant': 'vagrant/3',
            'custom1': {'id': 4, 'image': False},
            'custom2': {'id': 5, 'image': True},
            'custom3': {'id': 6, 'image': 'custom/image'},
        })
        conf.endpoints.update({
            'vagrant': 'https://vagrant_ep/api/',
        })
        conf.apikeys.update({
            'default': 32 * '1',
            'vagrant': 32 * '2',
        })
        conf.version = 'version'
    if target:
        if attr:
            patcher = mock.patch.object(target, attr, return_value=conf,
                                        autospec=True)
        else:
            patcher = mock.patch(target, return_value=conf, autospec=True)
    else:
        patcher = mock.patch('shub.config.load_shub_config', return_value=conf,
                             autospec=True)
    patcher.start()
    testcase.addCleanup(patcher.stop)
    return conf


def _is_tqdm_in_ascii_mode():
    """Small helper deciding about placeholders for tqdm progress bars."""
    with CliRunner().isolation():
        return not _supports_unicode(sys.stdout)


def format_expected_progress(progress):
    """Replace unicode symbols in progress string for tqdm in ascii mode."""
    if _is_tqdm_in_ascii_mode():
        to_replace = {'█': '#', '▏': '2', '▎': '3', '▌': '5', '▋': '6'}
        for sym in to_replace:
            progress = progress.replace(sym, to_replace[sym])
    return progress


def clean_progress_output(output):
    """Return output cleaned from \\r, \\n, and ANSI escape sequences"""
    return re.sub(
        r"""(?x)      # Matches:
        \n|\r|        # 1. newlines or carriage returns, or
        (\x1b\[|\x9b) # 2. ANSI control sequence introducer ("ESC[" or single
                      #    byte \x9b) +
        [^@-_]*[@-_]| #    private mode characters + command character, or
        \x1b[@-_]     # 3. ANSI control codes without sequence introducer
                      #    ("ESC"  + single command character)
        """,
        '', output)
