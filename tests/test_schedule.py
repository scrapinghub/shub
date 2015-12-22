import json
import unittest

import mock

from click import ClickException
from click.testing import CliRunner
from scrapinghub import APIError

from shub import schedule

from .utils import mock_conf


class ScheduleTest(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.conf = mock_conf(self)

    @mock.patch('shub.schedule.schedule_spider', autospec=True)
    def test_schedules_job_if_input_is_ok(self, mock_schedule):
        proj, endpoint, apikey = self.conf.get_target('default')
        # Default
        self.runner.invoke(schedule.cli, ['spider'])
        mock_schedule.assert_called_with(
            proj, endpoint, apikey, 'spider', (), ())
        # Other project
        self.runner.invoke(schedule.cli, ['123/spider'])
        mock_schedule.assert_called_with(
            123, endpoint, apikey, 'spider', (), ())
        # Other endpoint
        proj, endpoint, apikey = self.conf.get_target('vagrant')
        self.runner.invoke(schedule.cli, ['vagrant/spider'])
        mock_schedule.assert_called_with(
            proj, endpoint, apikey, 'spider', (), ())
        # Other project at other endpoint
        self.runner.invoke(schedule.cli, ['vagrant/456/spider'])
        mock_schedule.assert_called_with(
            456, endpoint, apikey, 'spider', (), ())

    @mock.patch('shub.schedule.Connection', autospec=True)
    def test_schedule_invalid_spider(self, mock_conn):
        mock_proj = mock_conn.return_value.__getitem__.return_value
        mock_proj.schedule.side_effect = APIError('')
        with self.assertRaises(ClickException):
            schedule.schedule_spider(1, 'https://endpoint/api/scrapyd',
                                     'FAKE_API_KEY', 'fake_spider')

    @mock.patch('shub.schedule.Connection', autospec=True)
    def test_schedule_spider_calls_project_schedule(self, mock_conn):
        mock_proj = mock_conn.return_value.__getitem__.return_value
        schedule.schedule_spider(1, 'https://endpoint/api/scrapyd',
                                 'FAKE_API_KEY', 'fake_spider')
        self.assertTrue(mock_proj.schedule.called)

    @mock.patch('shub.schedule.Connection', autospec=True)
    def test_forwards_args_and_settings(self, mock_conn):
        mock_proj = mock_conn.return_value.__getitem__.return_value
        self.runner.invoke(
            schedule.cli,
            "testspider -s SETT=99 -a ARG=val1 --set OTHERSETT=10 --argument "
            "OTHERARG=val2".split(' '),
        )
        call_kwargs = mock_proj.schedule.call_args[1]
        self.assertDictContainsSubset({'ARG': 'val1', 'OTHERARG': 'val2'},
                                      call_kwargs)
        # SH API expects settings as json-encoded string named 'job_settings'
        self.assertEqual({'SETT': '99', 'OTHERSETT': '10'},
                         json.loads(call_kwargs['job_settings']))


if __name__ == '__main__':
    unittest.main()
