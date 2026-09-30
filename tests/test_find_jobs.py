import unittest
from datetime import datetime
from unittest import mock

from click.testing import CliRunner

from shub import find_jobs
from shub.exceptions import BadParameterException

from .utils import AssertInvokeRaisesMixin, mock_conf


@mock.patch('shub.find_jobs.time.sleep')
@mock.patch('shub.find_jobs.get_scrapinghub_client_from_config')
class FindJobsTest(AssertInvokeRaisesMixin, unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        mock_conf(self)

    def _mock_jobs(self, mock_client, matches):
        client = mock_client.return_value
        project = client.get_project.return_value
        project.jobs.iter.return_value = [{'key': key} for key in matches]
        self.jobs = {
            key: mock.Mock(**{'requests.iter.return_value': iter(
                [{'url': 'x'}] if match else [])})
            for key, match in matches.items()
        }
        client.get_job.side_effect = self.jobs.__getitem__
        return project

    def test_find(self, mock_client, mock_sleep):
        project = self._mock_jobs(
            mock_client, {'1/1/3': True, '1/1/2': False, '1/1/1': True})
        result = self.runner.invoke(find_jobs.cli, (
            '--spider', 'amazon', '--since', '2026-09-01',
            '--filter', '["url", "contains", ["foo"]]',
        ))
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(result.output, '1/1/3\n1/1/1\n')
        project.jobs.iter.assert_called_once_with(
            spider='amazon',
            startts=int(datetime(2026, 9, 1).timestamp() * 1000),
            endts=None,
            count=101,
        )
        self.jobs['1/1/1'].requests.iter.assert_called_once_with(
            count=1, filter=['["url", "contains", ["foo"]]'])
        self.assertEqual(mock_sleep.call_args_list, [mock.call(1.0)] * 2)

    def test_max_jobs(self, mock_client, mock_sleep):
        self._mock_jobs(mock_client, {'1/1/3': True, '1/1/2': True})
        result = self.runner.invoke(find_jobs.cli, (
            '--spider', 'amazon', '--max-jobs', '1', '--filter', '[]',
        ))
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(result.stdout, '1/1/3\n')
        self.assertIn('Stopped after checking 1 jobs', result.stderr)

    def test_unbounded(self, mock_client, mock_sleep):
        self.assertInvokeRaises(BadParameterException, find_jobs.cli,
                                ('--filter', '[]'))
