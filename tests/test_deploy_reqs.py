#!/usr/bin/env python
# coding=utf-8

from __future__ import absolute_import
import unittest
import mock
import os
import tempfile

from click.testing import CliRunner

from shub import deploy_reqs

from .utils import mock_conf


class TestDeployReqs(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.conf = mock_conf(self)

    def test_can_decompress_downloaded_packages_and_call_deploy_reqs(self):
        requirements_file = self._write_tmp_requirements_file()
        with mock.patch('shub.utils.build_and_deploy_egg') as m:
            self.runner.invoke(
                deploy_reqs.cli,
                ('-r', requirements_file),
            )
            self.assertEqual(m.call_count, 2)
            for args, kwargs in m.call_args_list:
                project, endpoint, apikey = args
                self.assertEqual(project, 1)
                self.assertIn('https://app.scrapinghub.com', endpoint)
                self.assertEqual(apikey, self.conf.apikeys['default'])

    def _write_tmp_requirements_file(self):
        basepath = 'tests/samples/deploy_reqs_sample_project/'
        eggs = ['other-egg-0.2.1.zip', 'inflect-0.2.5.tar.gz']
        tmp_dir = tempfile.mkdtemp(prefix="shub-test-deploy-reqs")
        requirements_file = os.path.join(tmp_dir, 'requirements.txt')

        with open(requirements_file, 'w') as f:
            for egg in eggs:
                f.write(os.path.abspath(os.path.join(basepath, egg)) + "\n")

        return requirements_file


if __name__ == '__main__':
    unittest.main()
