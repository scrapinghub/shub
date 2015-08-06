#!/usr/bin/env python
# coding=utf-8

from __future__ import print_function

import unittest
import os
import tempfile
from mock import Mock, patch
from click.testing import CliRunner

from shub import deploy_reqs


class TestDeployReqs(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        os.environ['SHUB_APIKEY'] = '1234'

    def test_can_decompress_downloaded_packages_and_call_deploy_reqs(self):
        # GIVEN
        requirements_file = self._write_tmp_requirements_file()
        with self.runner.isolated_filesystem():
            # WHEN
            deploy_reqs.utils.build_and_deploy_egg = Mock()
            result = self.runner.invoke(deploy_reqs.cli, ["-p -1", requirements_file])

            # THEN
            err = 'Output: %s. Exception: %s' % (result.output, result.exception)
            self.assertEqual(2, deploy_reqs.utils.build_and_deploy_egg.call_count, err)


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
