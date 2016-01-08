#!/usr/bin/env python
# coding=utf-8

import unittest

from click.testing import CliRunner
from mock import patch

from shub import deploy
from shub.exceptions import NotFoundException

from .utils import AssertInvokeRaisesMixin, mock_conf


VALID_SCRAPY_CFG = """
[settings]
default = project.settings
"""


class DeployTest(AssertInvokeRaisesMixin, unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.conf = mock_conf(self, 'shub.deploy.load_shub_config')

    def _make_project(self):
        with open('scrapy.cfg', 'w') as f:
            f.write(VALID_SCRAPY_CFG)

    @patch('shub.deploy.make_deploy_request')
    def test_detect_scrapy_project(self, mock_deploy_req):
        with self.runner.isolated_filesystem():
            self.assertInvokeRaises(NotFoundException, deploy.cli)
            self._make_project()
            result = self.runner.invoke(deploy.cli)
            self.assertEqual(0, result.exit_code)

    @patch('shub.deploy.make_deploy_request')
    def _invoke_with_project(self, args, mock_deploy_req):
        with self.runner.isolated_filesystem():
            self._make_project()
            self.runner.invoke(deploy.cli, args)
        return mock_deploy_req.call_args[0]

    def test_fallback_to_default(self):
        url, data, files, auth, _, _ = self._invoke_with_project(None)
        self.assertIn(self.conf.endpoints['default'], url)
        self.assertEqual(data, {'project': 1, 'version': 'version'})
        self.assertEqual(auth, (self.conf.apikeys['default'], ''))

    def test_with_target(self):
        url, data, files, auth, _, _ = self._invoke_with_project(('prod', ))
        self.assertIn(self.conf.endpoints['default'], url)
        self.assertEqual(data, {'project': 2, 'version': 'version'})
        self.assertEqual(auth, (self.conf.apikeys['default'], ''))

    def test_with_id(self):
        url, data, files, auth, _, _ = self._invoke_with_project(('123', ))
        self.assertIn(self.conf.endpoints['default'], url)
        self.assertEqual(data, {'project': 123, 'version': 'version'})
        self.assertEqual(auth, (self.conf.apikeys['default'], ''))

    def test_with_external_id(self):
        url, data, files, auth, _, _ = self._invoke_with_project(
            ('vagrant/456', ))
        self.assertIn(self.conf.endpoints['vagrant'], url)
        self.assertEqual(data, {'project': 456, 'version': 'version'})
        self.assertEqual(auth, (self.conf.apikeys['vagrant'], ''))


if __name__ == '__main__':
    unittest.main()
