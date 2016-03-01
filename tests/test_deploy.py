#!/usr/bin/env python
# coding=utf-8

import unittest
import os

from click.testing import CliRunner
from mock import patch

from shub import deploy
from shub.exceptions import InvalidAuthException, NotFoundException

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

    @patch('shub.deploy.make_deploy_request')
    @patch('shub.deploy._has_project_access')
    def test_deploy_wizard(self, mock_project_access, mock_deploy_req):
        with self.runner.isolated_filesystem():
            self._make_project()
            with patch('shub.deploy._deploy_wizard') as mock_wizard:
                # Don't call when 'default' defined in the global conf
                self.runner.invoke(deploy.cli)
                self.assertFalse(mock_wizard.called)
                del self.conf.projects['default']
                # Don't call when non-default target was supplied
                self.runner.invoke(deploy.cli, 'not-default')
                self.assertFalse(mock_wizard.called)
            # Wizard is live from here on
            mock_project_access.return_value = False
            self.assertInvokeRaises(InvalidAuthException, deploy.cli,
                                    input='99\nn\n')
            # Don't create scrapinghub.yml if not wished
            mock_project_access.return_value = True
            self.runner.invoke(deploy.cli, input='99\nn\n')
            self.assertEqual(self.conf.projects['default'], 99)
            self.assertFalse(os.path.exists('scrapinghub.yml'))
            # Create scrapinghub.yml if wished
            del self.conf.projects['default']
            self.runner.invoke(deploy.cli, input='199\n\n')
            self.assertEqual(self.conf.projects['default'], 199)
            self.assertTrue(os.path.exists('scrapinghub.yml'))
            # Also run wizard when there's a scrapinghub.yml but no default
            # target
            del self.conf.projects['default']
            self.conf.projects['prod'] = 299
            self.runner.invoke(deploy.cli, input='399\n\n')
            self.assertEqual(self.conf.projects['default'], 399)


if __name__ == '__main__':
    unittest.main()
