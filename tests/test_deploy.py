#!/usr/bin/env python
# coding=utf-8


import unittest
from shub import deploy
from click.testing import CliRunner
from mock import patch


class DeployTest(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_fails_when_deploy_is_invoked_outside_of_a_scrapy_project(self):
        # given there's no scrapy.cfg file in the current folder
        with self.runner.isolated_filesystem():
            # when
            result = self.runner.invoke(deploy.cli)

            # then
            self.assertEqual(1, result.exit_code)

    @patch('shub.deploy.make_deploy_request')
    def test_parses_project_cfg_and_uploads_egg(self, deploy_req_mock):
        # given
        valid_scrapy_cfg = """
[deploy]
username = API_KEY
project = -1

[settings]
default = project.settings
"""
        with self.runner.isolated_filesystem():
            with open('scrapy.cfg', 'w') as f:
                f.write(valid_scrapy_cfg)

            # when
            result = self.runner.invoke(deploy.cli)

            # then
            self.assertTrue('Deploying to Scrapy Cloud' in result.output)
            self.assertEqual(0, result.exit_code)


if __name__ == '__main__':
    unittest.main()
