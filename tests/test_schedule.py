import mock
import unittest
from click import ClickException
from shub import schedule


class ScheduleTest(unittest.TestCase):

    @mock.patch('shub.schedule.HubstorageClient', spec=True)
    def test_schedule_spider_calls_push_job(self, mock_hs):
        mock_hs.return_value.get_project.return_value.ids.spider.return_value = 1
        mock_hs.return_value.push_job.return_value.key = mock.sentinel.jobkey
        jobkey = schedule.schedule_spider('FAKE_API_KEY', 1, 'fake_spider')
        self.assertEqual(jobkey, mock.sentinel.jobkey)

    @mock.patch('shub.schedule.HubstorageClient', spec=True)
    def test_schedule_spider_unknown_spider(self, mock_hs):
        mock_hs.return_value.get_project.return_value.ids.spider.return_value = None

        self.assertRaisesRegexp(
            ClickException, "Spider \'\w+\' doesn\'t exist in project \d+",
            schedule.schedule_spider, 'FAKE_API_KEY', 1, 'fake_spider'
        )


if __name__ == '__main__':
    unittest.main()
