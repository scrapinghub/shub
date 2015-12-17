#!/usr/bin/env python
# coding=utf-8

import unittest

from click.testing import CliRunner
from mock import patch

from shub import deploy
from shub.config import ShubConfig


TEST_APIKEY = '1' * 32

VALID_SCRAPY_CFG = """
[settings]
default = project.settings
"""

conf = ShubConfig()
conf.projects.update({'default': 1, 'external': 'ext/2'})
conf.endpoints.update({'ext': 'ext_endpoint/'})
conf.apikeys.update({'default': TEST_APIKEY, 'ext': 'extkey'})
conf.version = 'MyVersion'


class DeployTest(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def _make_project(self):
        with open('scrapy.cfg', 'w') as f:
            f.write(VALID_SCRAPY_CFG)

    @patch('shub.deploy.load_shub_config', return_value=conf)
    @patch('shub.deploy.make_deploy_request')
    def test_detect_scrapy_project(self, mock_deploy_req, mock_conf):
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(deploy.cli)
            self.assertEqual(1, result.exit_code)
            self._make_project()
            result = self.runner.invoke(deploy.cli)
            self.assertEqual(0, result.exit_code)

    @patch('shub.deploy.load_shub_config', return_value=conf)
    @patch('shub.deploy.make_deploy_request')
    def _invoke_with_project(self, args, mock_deploy_req, mock_conf):
        with self.runner.isolated_filesystem():
            self._make_project()
            self.runner.invoke(deploy.cli, args)
        return mock_deploy_req.call_args[0]

    def test_fallback_to_default(self):
        url, data, files, auth = self._invoke_with_project(None)
        self.assertIn(conf.endpoints['default'], url)
        self.assertEqual(data, {'project': 1, 'version': 'MyVersion'})
        self.assertEqual(auth, (TEST_APIKEY, ''))

    def test_with_target(self):
        url, data, files, auth = self._invoke_with_project(('external', ))
        self.assertIn(conf.endpoints['ext'], url)
        self.assertEqual(data, {'project': 2, 'version': 'MyVersion'})
        self.assertEqual(auth, ('extkey', ''))

    def test_with_id(self):
        url, data, files, auth = self._invoke_with_project(('123', ))
        self.assertIn(conf.endpoints['default'], url)
        self.assertEqual(data, {'project': 123, 'version': 'MyVersion'})
        self.assertEqual(auth, (TEST_APIKEY, ''))

    def test_with_external_id(self):
        url, data, files, auth = self._invoke_with_project(('ext/456', ))
        self.assertIn(conf.endpoints['ext'], url)
        self.assertEqual(data, {'project': 456, 'version': 'MyVersion'})
        self.assertEqual(auth, ('extkey', ''))


if __name__ == '__main__':
    unittest.main()
