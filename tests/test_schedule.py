import mock
import unittest
from click import ClickException
from click.testing import CliRunner
from shub import schedule
from scrapinghub import APIError


class ScheduleTest(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner(env={'SHUB_APIKEY': '1234'})

    @mock.patch('shub.schedule.schedule_spider', autospec=True)
    def test_schedules_job_if_input_is_ok(self, mock_schedule):
        def_target = (1, 'https://endpoint/api/scrapyd/', 'key')
        project, endpoint, apikey = def_target
        with mock.patch('shub.schedule.get_target') as mock_gt:
            mock_gt.return_value = def_target
            self.runner.invoke(schedule.cli, ['spider'])
            mock_gt.assert_called_with('default')
            mock_schedule.assert_called_with(project, endpoint, apikey, 'spider', ())
            # Spider from other project
            self.runner.invoke(schedule.cli, ['123/spider'])
            mock_gt.assert_called_with('123')
            mock_schedule.assert_called_with(project, endpoint, apikey, 'spider', ())

    @mock.patch('shub.schedule.Connection', spec=True)
    def test_schedule_spider_raises_click_exception_with_invalid_spider(self, mock_conn):
        mock_conn.return_value.__getitem__.return_value.id = 1
        mock_conn.return_value.__getitem__.return_value.schedule.side_effect = APIError('')
        with self.assertRaises(ClickException):
            schedule.schedule_spider(1, 'https://endpoint/api/scrapyd',
                                     'FAKE_API_KEY', 'fake_spider')

    @mock.patch('shub.schedule.Connection', spec=True)
    def test_schedule_spider_calls_project_schedule(self, mock_conn):
        mock_conn = mock_conn.return_value
        mock_conn.__getitem__.return_value.id = 1
        schedule.schedule_spider(1, 'https://endpoint/api/scrapyd', 'FAKE_API_KEY',
                                 'fake_spider')
        self.assertTrue(mock_conn.__getitem__.return_value.schedule.called)


if __name__ == '__main__':
    unittest.main()
