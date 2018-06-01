from __future__ import absolute_import
import json
import unittest

import mock

from click.testing import CliRunner
from scrapinghub import APIError

from shub import schedule
from shub.exceptions import RemoteErrorException

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
            proj, endpoint, apikey, 'spider', (), (), 2, 1, ())
        # Other project
        self.runner.invoke(schedule.cli, ['123/spider'])
        mock_schedule.assert_called_with(
            123, endpoint, apikey, 'spider', (), (), 2, 1, ())
        # Other endpoint
        proj, endpoint, apikey = self.conf.get_target('vagrant')
        self.runner.invoke(schedule.cli, ['vagrant/spider'])
        mock_schedule.assert_called_with(
            proj, endpoint, apikey, 'spider', (), (), 2, 1, ())
        # Other project at other endpoint
        self.runner.invoke(schedule.cli, ['vagrant/456/spider'])
        mock_schedule.assert_called_with(
            456, endpoint, apikey, 'spider', (), (), 2, 1, ())

    @mock.patch('shub.schedule.Connection', autospec=True)
    def test_schedule_invalid_spider(self, mock_conn):
        mock_proj = mock_conn.return_value.__getitem__.return_value
        mock_proj.schedule.side_effect = APIError('')
        with self.assertRaises(RemoteErrorException):
            schedule.schedule_spider(1, 'https://endpoint/api/',
                                     'FAKE_API_KEY', 'fake_spider')

    @mock.patch('shub.schedule.Connection', autospec=True)
    def test_schedule_spider_calls_project_schedule(self, mock_conn):
        mock_proj = mock_conn.return_value.__getitem__.return_value
        schedule.schedule_spider(1, 'https://endpoint/api/',
                                 'FAKE_API_KEY', 'fake_spider')
        self.assertTrue(mock_proj.schedule.called)

    @mock.patch('shub.schedule.Connection', autospec=True)
    def test_forwards_args_and_settings(self, mock_conn):
        mock_proj = mock_conn.return_value.__getitem__.return_value
        self.runner.invoke(
            schedule.cli,
            "testspider -s SETT=99 -a ARG=val1 --set SETTWITHEQUAL=10=10 "
            "--argument ARGWITHEQUAL=val2=val2".split(' '),
        )
        call_kwargs = mock_proj.schedule.call_args[1]
        self.assertDictContainsSubset(
            {'ARG': 'val1', 'ARGWITHEQUAL': 'val2=val2'},
            call_kwargs,
        )
        # SH API expects settings as json-encoded string named 'job_settings'
        self.assertEqual(
            {'SETT': '99', 'SETTWITHEQUAL': '10=10'},
            json.loads(call_kwargs['job_settings']),
        )

    @mock.patch('shub.schedule.Connection', autospec=True)
    def test_forwards_tags(self, mock_conn):
        mock_proj = mock_conn.return_value.__getitem__.return_value
        self.runner.invoke(schedule.cli, 'testspider -t tag1 -t tag2 --tag tag3'.split())
        call_kwargs = mock_proj.schedule.call_args[1]
        assert call_kwargs['add_tag'] == ('tag1', 'tag2', 'tag3')

    @mock.patch('shub.schedule.Connection', autospec=True)
    def test_forwards_priority_and_units(self, mock_conn):
        mock_proj = mock_conn.return_value.__getitem__.return_value
        # short option name
        self.runner.invoke(schedule.cli, 'testspider -p 3 -u 4'.split())
        call_kwargs = mock_proj.schedule.call_args[1]
        assert call_kwargs['priority'] == 3
        assert call_kwargs['units'] == 4
        # long option name
        self.runner.invoke(schedule.cli, 'testspider --priority 1 --units 3'.split())
        call_kwargs = mock_proj.schedule.call_args[1]
        assert call_kwargs['priority'] == 1
        assert call_kwargs['units'] == 3


if __name__ == '__main__':
    unittest.main()
