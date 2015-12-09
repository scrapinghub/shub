#!/usr/bin/env python
# coding=utf-8


import unittest

from mock import patch
from click.testing import CliRunner
from click import ClickException

from shub import utils


class UtilsTest(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def test_dependency_version_from_setup_is_parsed_properly(self):
        def check(cmd):
            if cmd == 'python setup.py --version':
                return setup_version

        setup_version = ('Building lxml version 3.4.4.'
                         '\nBuilding without Cython.'
                         '\nUsing build configuration of libxslt 1.1.28'
                         '\n3.4.4')

        with self.runner.isolated_filesystem():
            with patch('shub.utils.run', side_effect=check) as mocked_run:
                # given
                mocked_run.return_value = setup_version
                # when
                version = utils._get_dependency_version('lxml')
                # then
                self.assertEquals('lxml-3.4.4', version)

    def test_validate_jobid(self):
        invalid_job_ids = ['1/1', '123', '1/2/a', '1//']
        for job_id in invalid_job_ids:
            self.assertRaisesRegexp(
                ClickException,
                r'{} is invalid'.format(job_id),
                utils.validate_jobid, job_id,
            )

    @patch('shub.utils.find_api_key', return_value='my_api_key', autospec=True)
    @patch('shub.utils.HubstorageClient', autospec=True)
    def test_get_job(self, mock_HSC, mock_fak):
        class MockJob(object):
            metadata = {'some': 'val'}
        mockjob = MockJob()
        mock_HSC.return_value.get_job.return_value = mockjob

        self.assertIs(utils.get_job('1/1/1'), mockjob)
        mock_HSC.assert_called_once_with('my_api_key')

        with self.assertRaises(ClickException):
            utils.get_job('1/1/')

        # Non-existent job
        mockjob.metadata = None
        with self.assertRaises(ClickException):
            utils.get_job('1/1/1')


if __name__ == '__main__':
    unittest.main()
