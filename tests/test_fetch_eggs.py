import unittest
import mock
from collections import namedtuple

from click.testing import CliRunner
from shub import tool

FakeResponse = namedtuple('FakeResponse', ['status_code'])

@mock.patch('shub.fetch_eggs.requests', autospec=True)
class FetchEggsTest(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def test_raises_auth_exception(self, requests_mock):
        fake_response = FakeResponse(403)
        requests_mock.get.return_value = fake_response
        output = self.runner.invoke(tool.cli, ['fetch-eggs', 'xxx']).output
        self.assertTrue('Authentication failure' in output)

    def test_raises_exception_if_request_error(self, requests_mock):
        fake_response = FakeResponse(400)
        requests_mock.get.return_value = fake_response
        output = self.runner.invoke(tool.cli, ['fetch-eggs', 'xxx']).output
        self.assertTrue('Eggs could not be fetched' in output)
