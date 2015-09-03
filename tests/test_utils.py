#!/usr/bin/env python
# coding=utf-8


import unittest
from mock import patch
from shub import utils
from click.testing import CliRunner


class UtilsTest(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_dependency_version_from_setup_is_parsed_properly(self):
        def check(cmd):
            if cmd == 'python setup.py --version':
                return setup_version

        setup_version = ('Building lxml version 3.4.4.'
                         '\nBuilding without Cython.'
                         '\nUsing build configuration of libxslt 1.1.28'
                         '\n3.4.4')

        with self.runner.isolated_filesystem():
            with patch('shub.utils.run', side_effect=check) as mocked_run:
                # given
                mocked_run.return_value = setup_version
                # when
                version = utils._get_dependency_version('lxml')
                # then
                self.assertEquals('lxml-3.4.4', version)


if __name__ == '__main__':
    unittest.main()
