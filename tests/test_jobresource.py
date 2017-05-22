# -*- coding: utf-8 -*-
from __future__ import absolute_import
import mock
import unittest
import time
import json

from click.testing import CliRunner

from shub import items, log, requests, jobmeta, stats


class JobResourceTest(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def _test_prints_objects(self, cmd_mod, resource_name):
        objects = ['Object 1', 'Object 2']
        jobid = '1/2/3'
        with mock.patch.object(cmd_mod, 'get_job', autospec=True) as mock_gj:
            # Patch job.items.iter_json() to return our objects
            mock_gj.return_value._metadata_updated = time.time()
            mock_resource = getattr(mock_gj.return_value, resource_name)
            mock_resource.iter_json.return_value = objects
            result = self.runner.invoke(cmd_mod.cli, (jobid,))
            mock_gj.assert_called_once_with(jobid)
            self.assertIn("\n".join(objects), result.output)

    def _test_forwards_follow(self, cmd_mod):
        with mock.patch.object(cmd_mod, 'get_job'), \
             mock.patch.object(cmd_mod, 'job_resource_iter', autospec=True) \
             as mock_jri:
            self.runner.invoke(cmd_mod.cli, ('1/2/3',))
            self.assertFalse(mock_jri.call_args[1]['follow'])
            self.runner.invoke(cmd_mod.cli, ('1/2/3', '-f'))
            self.assertTrue(mock_jri.call_args[1]['follow'])

    def _test_mock_jobmeta(self, cmd_mod, mocked_value, expected_result):
        jobid = '1/2/3'
        with mock.patch.object(cmd_mod, 'get_job', autospec=True) as mock_gj:
            mock_gj.return_value._metadata_updated = time.time()
            mock_gj.return_value = mock.PropertyMock(metadata=mocked_value)
            result = self.runner.invoke(cmd_mod.cli, (jobid,))
            mock_gj.assert_called_once_with(jobid)
            self.assertEqual(expected_result, json.loads(result.output))

    def test_items(self):
        self._test_prints_objects(items, 'items')
        self._test_forwards_follow(items)

    def test_requests(self):
        self._test_prints_objects(requests, 'requests')
        self._test_forwards_follow(requests)

    def test_jobmeta(self):
        mocked_jobmeta = {'foo': 'bar'}
        self._test_mock_jobmeta(jobmeta, mocked_jobmeta, mocked_jobmeta)

    def test_stats(self):
        # For jobs without metadata, e.g. those are pending or cancelled
        # before running
        mocked_jobmeta = {'foo': 'bar'}
        self._test_mock_jobmeta(stats, mocked_jobmeta, {})
        # For jobs with metadata
        mocked_jobmeta['scrapystats'] = {'bar': 'baz'}
        self._test_mock_jobmeta(stats, mocked_jobmeta, mocked_jobmeta['scrapystats'])

    def test_log(self):
        objects = [
            {'time': 0, 'level': 20, 'message': 'message 1'},
            {'time': 1450874471000, 'level': 50, 'message': 'message 2'},
        ]
        jobid = '1/2/3'
        with mock.patch.object(log, 'get_job', autospec=True) as mock_gj:
            mock_gj.return_value._metadata_updated = time.time()
            mock_gj.return_value.logs.iter_values.return_value = objects
            result = self.runner.invoke(log.cli, (jobid,))
            mock_gj.assert_called_once_with(jobid)
            self.assertIn('1970-01-01 00:00:00 INFO message 1', result.output)
            self.assertIn('2015-12-23 12:41:11 CRITICAL message 2', result.output)
        with mock.patch.object(log, 'get_job', autospec=True) as mock_gj:
            with mock.patch.object(log, 'job_resource_iter', autospec=True) as mock_res_iter:
                mock_res_iter.return_value = [json.dumps(x) for x in objects]
                result = self.runner.invoke(log.cli, (jobid, '--json'))
                self.assertTrue(mock_res_iter.call_args[1].get('output_json'))
                for idx, line in enumerate(result.output.splitlines()):
                    self.assertEqual(json.loads(line), objects[idx])
        self._test_forwards_follow(log)

    def test_log_unicode(self):
        objects = [
            {'time': 0, 'level': 20, 'message': u'jarzębina'}
        ]
        jobid = '1/2/3'
        with mock.patch.object(log, 'get_job', autospec=True) as mock_gj:
            mock_gj.return_value._metadata_updated = time.time()
            mock_gj.return_value.logs.iter_values.return_value = objects
            result = self.runner.invoke(log.cli, (jobid,))
            mock_gj.assert_called_once_with(jobid)
            self.assertIn(u'1970-01-01 00:00:00 INFO jarzębina', result.output)


if __name__ == '__main__':
    unittest.main()
