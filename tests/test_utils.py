#!/usr/bin/env python
# coding=utf-8


import unittest

from mock import patch
from click.testing import CliRunner
from collections import deque

from shub import utils
from shub.exceptions import BadParameterException, NotFoundException

from .utils import mock_conf


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

    def test_get_job_specs(self):
        conf = mock_conf(self)
        def _test_specs(job, expected_job_id, expected_endpoint):
            self.assertEqual(
                utils.get_job_specs(job),
                (expected_job_id, conf.get_apikey(expected_endpoint)),
            )
        _test_specs('10/20/30', '10/20/30', 'default')
        _test_specs('2/3', '1/2/3', 'default')
        _test_specs('default/2/3', '1/2/3', 'default')
        _test_specs('prod/2/3', '2/2/3', 'default')
        _test_specs('vagrant/2/3', '3/2/3', 'vagrant')

    def test_get_job_specs_validates_jobid(self):
        invalid_job_ids = ['/1/1', '123', '1/2/a', '1//']
        for job_id in invalid_job_ids:
            with self.assertRaises(BadParameterException):
                utils.get_job_specs(job_id)

    @patch('shub.utils.HubstorageClient', autospec=True)
    def test_get_job(self, mock_HSC):
        class MockJob(object):
            metadata = {'some': 'val'}
        mockjob = MockJob()
        mock_HSC.return_value.get_job.return_value = mockjob
        conf = mock_conf(self)

        self.assertIs(utils.get_job('1/1/1'), mockjob)
        mock_HSC.assert_called_once_with(auth=conf.apikeys['default'])

        with self.assertRaises(BadParameterException):
            utils.get_job('1/1/')

        # Non-existent job
        mockjob.metadata = None
        with self.assertRaises(NotFoundException):
            utils.get_job('1/1/1')

    def test_is_deploy_successful(self):
        # no results
        last_logs = deque(maxlen=5)
        assert not utils._is_deploy_successful(last_logs)
        # missing or incorrect data
        last_logs.append("")
        assert not utils._is_deploy_successful(last_logs)
        last_logs.append("abcdef")
        assert not utils._is_deploy_successful(last_logs)
        last_logs.append('{"field":"wrong"}')
        assert not utils._is_deploy_successful(last_logs)
        # error status
        last_logs.append('{"status":"error"}')
        assert not utils._is_deploy_successful(last_logs)
        # successful status
        last_logs.append('{"status":"ok"}')
        assert utils._is_deploy_successful(last_logs)
        last_logs.append('{"field":"value","status":"ok"}')
        assert utils._is_deploy_successful(last_logs)
        # more complex python expression
        last_logs.append('{"status":"ok", "project": 1111112, '
                         '"version": "1234-master", "spiders": 3}')
        assert utils._is_deploy_successful(last_logs)


if __name__ == '__main__':
    unittest.main()
