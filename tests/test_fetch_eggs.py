import os
import unittest
from pathlib import Path
from typing import NamedTuple
from unittest import mock

from click.testing import CliRunner

from shub import fetch_eggs
from shub.exceptions import InvalidAuthException, RemoteErrorException, ShubException

from .utils import AssertInvokeRaisesMixin, mock_conf


class FakeResponse(NamedTuple):
    status_code: int


@mock.patch("shub.fetch_eggs.requests", autospec=True)
class FetchEggsTest(AssertInvokeRaisesMixin, unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.conf = mock_conf(self)

    def test_raises_auth_exception(self, requests_mock):
        fake_response = FakeResponse(403)
        requests_mock.get.return_value = fake_response
        self.assertInvokeRaises(InvalidAuthException, fetch_eggs.cli)

    def test_raises_exception_if_request_error(self, requests_mock):
        fake_response = FakeResponse(400)
        requests_mock.get.return_value = fake_response
        self.assertInvokeRaises(RemoteErrorException, fetch_eggs.cli)

    @unittest.skipIf(os.name == "nt", "creating symbolic links needs privileges")
    def test_does_not_write_through_a_symlink(self, requests_mock):
        requests_mock.get.return_value = mock.Mock(
            status_code=200, iter_content=lambda chunk_size: [b"data"]
        )
        with self.runner.isolated_filesystem():
            Path("eggs-1.zip").symlink_to(Path("victim").absolute())
            self.assertInvokeRaises(ShubException, fetch_eggs.cli)
            assert not Path("victim").exists()
