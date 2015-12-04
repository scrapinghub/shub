from collections import namedtuple
import mock
import unittest
from click import ClickException
from click.testing import CliRunner
from shub import items


Job = namedtuple('Job', ['items', 'metadata'])
Item = namedtuple('Item', ['iter_values'])


class ItemsTest(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def test_cli_raises_invalid_jobid(self):
        output = self.runner.invoke(items.cli, ['123']).output
        err = 'Unexpected output: %s' % output
        self.assertTrue('Invalid job ID' in output, err)

    @mock.patch('shub.items.find_api_key', autospec=True)
    def test_apikey_is_validated(self, mock_find_apikey):
        mock_find_apikey.return_value = None
        output = self.runner.invoke(items.cli, ['1/1/1']).output
        err = 'Unexpected output: %s' % output
        self.assertTrue('key not found' in output, err)

    @mock.patch('shub.items.find_api_key', autospec=True)
    @mock.patch('shub.items.fetch_items_for_job', autospec=True)
    def test_fetches_items_if_input_is_ok(self, mock_find_apikey, mock_fetch_items_for_job):
        mock_find_apikey.return_value = 1
        self.runner.invoke(items.cli, ['1/1/1'])
        self.assertTrue(mock_fetch_items_for_job.called)

    @mock.patch('shub.items.HubstorageClient', spec=True)
    def test_fetch_items_for_job_with_invalid_job(self, mock_hs):
        job = Job(Item(lambda: []), None)
        mock_hs.return_value.get_job.return_value = job
        self.assertRaisesRegexp(
            ClickException, 'The job -1/-1/-1 doesn\'t exist',
            items.fetch_items_for_job, 'FAKE_API_KEY', '-1/-1/-1'
        )

    @mock.patch('shub.items.HubstorageClient', spec=True)
    def test_fetch_items_for_job_with_valid_job(self, mock_hs):
        mock_hs.return_value.get_job.return_value = Job(Item(lambda: []), 1)
        result = items.fetch_items_for_job('FAKE_API_KEY', '1/1/1')
        self.assertListEqual([], result)


if __name__ == '__main__':
    unittest.main()
