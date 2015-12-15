import unittest
import mock
from collections import namedtuple

from click.testing import CliRunner
from shub import tool

FakeResponse = namedtuple('FakeResponse', ['status_code'])

@mock.patch('shub.fetch_eggs.requests', autospec=True)
class FetchEggsTest(unittest.TestCase):

    def setUp(self):
        # defining SHUB_APIKEY so it passes the login validation
        self.runner = CliRunner(env={'SHUB_APIKEY': 'xxx'})

    def test_raises_auth_exception(self, requests_mock):
        fake_response = FakeResponse(403)
        requests_mock.get.return_value = fake_response
        output = self.runner.invoke(tool.cli, ['fetch-eggs', '100']).output
        err = 'Unexpected output: %s' % output
        self.assertTrue('Authentication failure' in output, err)

    def test_raises_exception_if_request_error(self, requests_mock):
        fake_response = FakeResponse(400)
        requests_mock.get.return_value = fake_response
        output = self.runner.invoke(tool.cli, ['fetch-eggs', '100']).output
        err = 'Unexpected output: %s' % output
        self.assertTrue('Eggs could not be fetched' in output, err)
