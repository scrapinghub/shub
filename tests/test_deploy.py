#!/usr/bin/env python
# coding=utf-8

from __future__ import absolute_import

import unittest
import os

import pytest
from click.testing import CliRunner
from mock import patch

from shub import deploy
from shub.config import ShubConfig
from shub.exceptions import InvalidAuthException, NotFoundException, \
    ShubException, BadParameterException

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

    def test_deploy_list_targets(self):
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(deploy.cli, ('--list-targets',))
            assert result.exit_code == 0

    @patch('shub.deploy.deploy_cmd')
    def test_custom_deploy_disabled(self, mock_deploy_cmd):
        with self.runner.isolated_filesystem():
            self._make_project()
            self.runner.invoke(deploy.cli, ('custom1',))
        self.assertTrue(mock_deploy_cmd.called)

    @patch('shub.deploy.upload_cmd')
    def test_custom_deploy_default(self, mock_upload_cmd):
        with self.runner.isolated_filesystem():
            self._make_project()
            self.runner.invoke(deploy.cli, ('custom2',))
        self.assertEqual(mock_upload_cmd.call_args[0], ('custom2', None))

    @patch('shub.deploy.upload_cmd')
    def test_custom_deploy_by_id(self, mock_upload_cmd):
        with self.runner.isolated_filesystem():
            self._make_project()
            self.runner.invoke(deploy.cli, ('5',))
        mock_upload_cmd.assert_called_once_with('5', None)

    def test_custom_deploy_bad_registry(self):
        with self.runner.isolated_filesystem():
            self._make_project()
            self.assertInvokeRaises(BadParameterException, deploy.cli, ('custom3',))


class DeployFilesTest(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.request = patch('shub.deploy.make_deploy_request').start()
        self.addCleanup(patch.stopall)

    def _deploy(self, main_egg='./main.egg', req='./requirements.txt',
                eggs=None):
        if eggs is None:
            eggs = ['./1.egg', './2.egg']

        deploy._upload_egg(
            'endpoint',
            main_egg,
            '1', 'version', 'auth',
            False, False,
            requirements_file=req,
            eggs=eggs,
        )
        files = {}
        for name, file in self.request.call_args[0][2]:
            files.setdefault(name, []).append(file.read().decode('utf-8'))

        return files

    def test_correct_files(self):
        with self.runner.isolated_filesystem():
            with open('./main.egg', 'w') as f:
                f.write('main content')
            with open('./requirements.txt', 'w') as f:
                f.write('requirements content')
            with open('./1.egg', 'w') as f:
                f.write('1.egg content')
            with open('./2.egg', 'w') as f:
                f.write('2.egg content')
            files = self._deploy()

        self.assertEqual(files['egg'][0], 'main content')
        self.assertEqual(files['requirements'][0], 'requirements content')
        self.assertEqual(files['eggs'][0], '1.egg content')
        self.assertEqual(files['eggs'][1], '2.egg content')

    def test_no_egg(self):
        with self.runner.isolated_filesystem():
            with open('./main.egg', 'w') as f:
                f.write('main content')
            with open('./requirements.txt', 'w') as f:
                f.write('requirements content')
            with open('./1.egg', 'w') as f:
                f.write('1.egg content')

            with self.assertRaises(ShubException) as cm:
                self._deploy()

            self.assertEqual(
                cm.exception.message,
                'No such file or directory ./2.egg',
            )

    def test_no_requirements(self):
        with self.runner.isolated_filesystem():
            with open('./main.egg', 'w') as f:
                f.write('main content')
            with open('./1.egg', 'w') as f:
                f.write('1.egg content')
            with open('./2.egg', 'w') as f:
                f.write('2.egg content')

            with self.assertRaises(ShubException) as cm:
                self._deploy()

            self.assertEqual(
                cm.exception.message,
                'No such file or directory ./requirements.txt',
            )

    def test_egg_glob_pattern(self):
        with self.runner.isolated_filesystem():
            with open('./main.egg', 'w') as f:
                f.write('main content')
            with open('./a1.egg', 'w') as f:
                f.write('a1.egg content')
            with open('./a2.egg', 'w') as f:
                f.write('a2.egg content')
            with open('./b3.egg', 'w') as f:
                f.write('b3.egg content')
            files_a = self._deploy(eggs=['./a*.egg'], req=None)
            files_c = self._deploy(eggs=['./c*.egg'], req=None)
            files_all = self._deploy(eggs=['./*.egg'], req=None)
            files_main = self._deploy(eggs=['./main.egg', './*.egg'], req=None)

        self.assertEqual(len(files_a['eggs']), 2)
        self.assertIn('a1.egg content', files_a['eggs'])
        self.assertIn('a2.egg content', files_a['eggs'])
        self.assertNotIn('eggs', files_c)

        # main egg should not be added to eggs even it it matches glob pattern
        self.assertEqual(len(files_all['eggs']), 3)
        self.assertIn('a1.egg content', files_all['eggs'])
        self.assertIn('a2.egg content', files_all['eggs'])
        self.assertIn('b3.egg content', files_all['eggs'])

        # but do upload the main egg if it's directly requested
        self.assertEqual(len(files_main['eggs']), 4)
        self.assertIn('main content', files_main['eggs'])


if __name__ == '__main__':
    unittest.main()
