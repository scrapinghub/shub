import unittest
from unittest.mock import patch

import requests
from click.testing import CliRunner

from shub import list_stacks

from .test_utils import _tags_response


TAGS = ['2.19-rc1', '2.14', '2.9-20230720', '2.18-20260801', '2.10-20230901',
        '2.18-20260824', '1.8-py3-20191203']


@patch('shub.utils.requests.get', autospec=True)
class ListStacksTest(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def test_latest_per_version(self, mock_get):
        mock_get.return_value = _tags_response(TAGS)
        result = self.runner.invoke(list_stacks.cli)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'scrapy:2.18-20260824\n'
            'scrapy:2.10-20230901\n'
            'scrapy:2.9-20230720\n',
        )

    def test_all(self, mock_get):
        mock_get.return_value = _tags_response(TAGS)
        result = self.runner.invoke(list_stacks.cli, ['--all'])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            'scrapy:2.18-20260824\n'
            'scrapy:2.18-20260801\n'
            'scrapy:2.10-20230901\n'
            'scrapy:2.9-20230720\n',
        )

    def test_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError('offline')
        result = self.runner.invoke(list_stacks.cli)
        self.assertEqual(result.exit_code, 76)
        self.assertIn('offline', result.output)
        self.assertIn(list_stacks.TAGS_URL, result.output)
