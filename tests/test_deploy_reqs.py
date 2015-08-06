#!/usr/bin/env python
# coding=utf-8

from __future__ import print_function

import unittest
import os
import tempfile
from mock import Mock, patch
from click.testing import CliRunner

from shub import deploy_reqs


@patch('shub.deploy_reqs.utils.build_and_deploy_egg')
class TestDeployReqs(unittest.TestCase):
    VALID_APIKEY = '1234'

    def setUp(self):
        self.runner = CliRunner()
        os.environ['SHUB_APIKEY'] = self.VALID_APIKEY

    def test_can_decompress_downloaded_packages_and_call_deploy_reqs(self, deploy_egg_mock):
        # GIVEN
        requirements_file = self._write_tmp_requirements_file()

        with self.runner.isolated_filesystem():
            # WHEN
            result = self.runner.invoke(deploy_reqs.cli, ["-p -1", requirements_file])

            # THEN
            self.assertEqual(2, deploy_egg_mock.call_count, self.error_for(result))

    def test_uses_project_id_from_scrapy_cfg_per_default(self, deploy_egg_mock):
        requirements_file = self._write_tmp_requirements_file()
        with self.runner.isolated_filesystem():
            # GIVEN
            self.write_valid_scrapy_cfg()

            # WHEN I don't provide the project id
            self.runner.invoke(deploy_reqs.cli, [requirements_file])

            # THEN It uses the project id in the scrapy.cfg file
            deploy_egg_mock.assert_called_with('-1', self.VALID_APIKEY)

    def _write_tmp_requirements_file(self):
        basepath = 'tests/samples/deploy_reqs_sample_project/'
        eggs = ['other-egg-0.2.1.zip', 'inflect-0.2.5.tar.gz']
        tmp_dir = tempfile.mkdtemp(prefix="shub-test-deploy-reqs")
        requirements_file = os.path.join(tmp_dir, 'requirements.txt')

        with open(requirements_file, 'w') as f:
            for egg in eggs:
                f.write(os.path.abspath(os.path.join(basepath, egg)) + "\n")

        return requirements_file

    def write_valid_scrapy_cfg(self):

        valid_scrapy_cfg = """
[deploy]
username = API_KEY
project = -1

[settings]
default = project.settings
"""
        with open('scrapy.cfg', 'w') as f:
            f.write(valid_scrapy_cfg)

    def error_for(self, result):
        return '\nOutput: %s.\nException: %s' % (result.output.strip(), repr(result.exception))


if __name__ == '__main__':
    unittest.main()
