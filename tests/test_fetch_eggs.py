from __future__ import absolute_import
import unittest

from collections import namedtuple

import mock

from click.testing import CliRunner

from shub import fetch_eggs
from shub.exceptions import InvalidAuthException, RemoteErrorException

from .utils import AssertInvokeRaisesMixin, mock_conf


FakeResponse = namedtuple('FakeResponse', ['status_code'])


@mock.patch('shub.fetch_eggs.requests', autospec=True)
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
