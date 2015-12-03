import mock
import unittest
from click import ClickException
from shub import items


class ItemsTest(unittest.TestCase):

    @mock.patch('shub.items.HubstorageClient', spec=True)
    def test_fetch_items_for_job_with_invalid_job(self, mock_hs):
        mock_hs.return_value.get_job.return_value.metadata = None
        self.assertRaisesRegexp(
            ClickException, 'The job -1/-1/-1 doesn\'t exist',
            items.fetch_items_for_job, 'FAKE_API_KEY', '-1/-1/-1'
        )

    @mock.patch('shub.items.HubstorageClient', spec=True)
    def test_fetch_items_for_job_with_valid_job(self, mock_hs):
        mock_hs.return_value.get_job.return_value.metadata = 1
        items.fetch_items_for_job('FAKE_API_KEY', '1/1/1')
        fake_job = mock_hs.return_value.get_job.return_value
        self.assertTrue(fake_job.items.iter_values.called)


if __name__ == '__main__':
    unittest.main()
