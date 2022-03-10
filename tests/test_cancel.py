from __future__ import absolute_import

import unittest
from collections import namedtuple
from unittest import mock

from click.testing import CliRunner

from shub import cancel
from shub.exceptions import (
    BadParameterException,
    ShubException,
)

from .utils import AssertInvokeRaisesMixin, mock_conf


class CancelTest(AssertInvokeRaisesMixin, unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.conf = mock_conf(self)

    @mock.patch('shub.cancel.get_scrapinghub_client_from_config')
    def test_simple_cancel_call(self, mock_client):
        client = mock_client.return_value
        mock_proj = client.get_project.return_value
        mock_proj.jobs.cancel.return_value = {'count': 2}

        result = self.runner.invoke(
            cancel.cli, ('123456', '1/1', '1/2',), input='y\n'
        )

        self.assertTrue("{'count': 2}" in result.output)
        self.assertEqual(0, result.exit_code)
        self.assertEqual(mock_proj.jobs.cancel.call_count, 1)
        mock_proj.jobs.cancel.assert_called_with(
            keys=['123456/1/1', '123456/1/2']
        )

    @mock.patch('shub.cancel.get_target_conf')
    @mock.patch('shub.cancel.get_scrapinghub_client_from_config')
    def test_cancel_default_project(self, mock_client, targetconf):
        client = mock_client.return_value
        mock_proj = client.get_project.return_value
        mock_proj.jobs.cancel.return_value = {'count': 2}

        Target = namedtuple('Target', 'project_id')
        targetconf.return_value = Target(project_id='123456')

        result = self.runner.invoke(
            cancel.cli, ('1/1', '1/2',), input='y\n'
        )

        self.assertTrue("{'count': 2}" in result.output)
        self.assertEqual(0, result.exit_code)
        self.assertEqual(mock_proj.jobs.cancel.call_count, 1)
        mock_proj.jobs.cancel.assert_called_with(
            keys=['123456/1/1', '123456/1/2']
        )

    @mock.patch('shub.cancel.get_scrapinghub_client_from_config')
    def test_invalid_job_key(self, mock_client):
        self.assertInvokeRaises(
            SystemExit,
            cancel.cli,
            ('123456', '1/1', '1',),
            input='y\n'
        )

        self.assertInvokeRaises(
            SystemExit,
            cancel.cli,
            ('123456', '1/abc', '1',),
            input='y\n'
        )

    @mock.patch('shub.cancel.get_scrapinghub_client_from_config')
    def test_cancel_failure(self, mock_client):
        client = mock_client.return_value
        mock_proj = client.get_project.return_value
        mock_proj.jobs.cancel.side_effect = ValueError('Error msg')

        self.assertInvokeRaises(
            ShubException,
            cancel.cli,
            ('123456', '1/1', '1/2',),
            input='y\n',
        )

    @mock.patch('shub.cancel.get_scrapinghub_client_from_config')
    def test_cancel_abort(self, mock_client):
        client = mock_client.return_value
        client.get_project.return_value

        result = self.runner.invoke(
            cancel.cli, ('123456', '1/1', '1/2',), input='N\n',
        )
        self.assertTrue('Aborted!' in result.output)

    def test_validate_job_key(self):
        with self.assertRaises(BadParameterException):
            cancel.validate_job_key('123456', '1')

        with self.assertRaises(BadParameterException):
            cancel.validate_job_key('123456', '1/abc')

        with self.assertRaises(BadParameterException):
            cancel.validate_job_key('123456', '')


if __name__ == '__main__':
    unittest.main()
