#!/usr/bin/env python
# coding=utf-8


import unittest
from shub import deploy
from click.testing import CliRunner
from mock import patch

TEST_APIKEY = '1' * 32

VALID_SCRAPY_CFG = """
[deploy]
username = %s
project = -1

[settings]
default = project.settings
""" % TEST_APIKEY


class DeployTest(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner(env={'SHUB_APIKEY': '123'})

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
        with self.runner.isolated_filesystem():
            with open('scrapy.cfg', 'w') as f:
                f.write(VALID_SCRAPY_CFG)

            # when
            result = self.runner.invoke(deploy.cli)

            # then
            err = 'Output: %s\nException: %s' % (result.output, result.exception)
            self.assertEqual(0, result.exit_code, err)

    @patch('shub.deploy.make_deploy_request')
    def test_makes_a_deploy_request_using_the_values_in_scrapycfg(self, deploy_req_mock):
        # given
        with self.runner.isolated_filesystem():
            with open('scrapy.cfg', 'w') as f:
                f.write(VALID_SCRAPY_CFG)

            # when
            self.runner.invoke(deploy.cli)

            # then
            url, data, files, auth = deploy_req_mock.call_args[0]
            err = 'The scrapy.cfg username should have been used as the apikey'
            self.assertEquals((TEST_APIKEY, ''), auth, err)

            err = 'The project specified in the scrapy.cfg file should have been used'
            self.assertEquals(-1, data['project'], err)


if __name__ == '__main__':
    unittest.main()
