#!/usr/bin/env python
# coding=utf-8

import unittest
from click.testing import CliRunner
from shub import tool
import os


@unittest.skipUnless(os.getenv('USING_TOX'),
                     'End to end tests only run via TOX')
class ShubEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def run_subcmd(self, subcmd):
        return self.runner.invoke(tool.cli, [subcmd]).output

    def test_usage_is_displayed_if_no_arg_is_provided(self):
        output = self.run_subcmd('')
        usage_is_displayed = output.startswith('Usage:')
        self.assertTrue(usage_is_displayed)

    def test_deploy_egg_isnt_broken(self):
        output = self.run_subcmd('deploy-egg')
        error = 'Unexpected output: %s' % output
        self.assertTrue('Missing argument' in output, error)

    def test_deploy_reqs_isnt_broken(self):
        output = self.run_subcmd('deploy-reqs')
        error = 'Unexpected output: %s' % output
        self.assertTrue('Missing argument' in output, error)

    def test_deploy_isnt_broken(self):
        output = self.run_subcmd('deploy')
        error = 'Unexpected output: %s' % output
        self.assertTrue('requires scrapy' in output, error)

    def test_fetch_eggs_isnt_broken(self):
        output = self.run_subcmd('fetch-eggs')
        error = 'Unexpected output: %s' % output
        self.assertTrue('Missing argument' in output, error)
