import mock
import unittest

from click.testing import CliRunner

from shub import items, log, requests


class JobResourceTest(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def _test_prints_objects(self, cmd_mod, resource_name):
        objects = ['Object 1', 'Object 2']
        jobid = '1/2/3'
        with mock.patch.object(cmd_mod, 'get_job', autospec=True) as mock_gj:
            # Patch job.items.iter_values() to return our objects
            mock_resource = getattr(mock_gj.return_value, resource_name)
            mock_resource.iter_values.return_value = objects
            result = self.runner.invoke(cmd_mod.cli, (jobid,))
            mock_gj.assert_called_once_with(jobid)
            self.assertIn("\n".join(objects), result.output)

    def test_items(self):
        self._test_prints_objects(items, 'items')

    def test_log(self):
        self._test_prints_objects(log, 'logs')

    def test_requests(self):
        self._test_prints_objects(requests, 'requests')


if __name__ == '__main__':
    unittest.main()
