#!/usr/bin/env python


import os
import sys
import unittest
from unittest.mock import patch, Mock

import requests
from click.testing import CliRunner

from shub import deploy
from shub.exceptions import (
    NotFoundException, ShubException, BadParameterException,
    DeployRequestTooLargeException,
)
from shub.utils import create_default_setup_py, _SETUP_PY_TEMPLATE

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

    @patch('shub.deploy.make_deploy_request')
    def test_deploy_with_custom_setup_py(self, mock_deploy_req):
        with self.runner.isolated_filesystem():
            # This scrapy.cfg contains no "settings" section, so creating a
            # default setup.py would fail (because we can't find the settings
            # module)
            open('scrapy.cfg', 'w').close()
            # However, we already have a setup.py...
            create_default_setup_py(settings='some_module')
            # ... so shub should not fail while trying to create one
            result = self.runner.invoke(deploy.cli)
            self.assertEqual(result.exit_code, 0)

    @patch('shub.utils.requests')
    @patch('shub.utils.write_and_echo_logs')
    def test_deploy_with_single_large_file(self, mock_logs, mock_requests):
        with self.runner.isolated_filesystem():
            self._make_project()
            # patch setup_py to include package data files
            setup_py = _SETUP_PY_TEMPLATE % {'settings': 'project.settings'}
            setup_py = setup_py.rsplit('\n', 2)[0]  # drop an enclosing brace
            setup_py += '    include_package_data = True)'
            with open('setup.py', 'w') as setup_file:
                setup_file.write(setup_py)
            # create a fake package and add a large random file there
            os.mkdir('files')
            open('files/__init__.py', 'wb').close()
            with open('files/file.large', 'wb') as bigfile:
                bigfile.write(os.urandom(50 * 1024 * 1024))
            # add manifest to include the non-code file
            with open('MANIFEST.in', 'w') as manifest_f:
                manifest_f.write('include files/file.large')
            fake_response = requests.Response()
            fake_response.status_code = 200
            mock_requests.post.return_value = fake_response
            self.assertInvokeRaises(DeployRequestTooLargeException,
                                    deploy.cli)


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
            files.setdefault(name, []).append(
                file if isinstance(file, str)
                else file.read().decode('utf-8'))

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

    def test_add_sources(self):
        convert_deps_to_pip = Mock(
            side_effect=[
                './requirements.txt',
                ['package==0.0.0', 'hash-package==0.0.1', 'hash-package2==0.0.1'],
            ],
        )
        _sources = (
            b'-i https://pypi.python.org/simple '
            b'--extra-index-url https://example.external-index.org/simple'
        )
        self.assertIsInstance(deploy._add_sources(convert_deps_to_pip(), _sources), str)
        self.assertIsInstance(deploy._add_sources(convert_deps_to_pip(), _sources), str)

    def pipfile_test(self, req_name):
        with self.runner.isolated_filesystem():
            with open('./main.egg', 'w') as f:
                f.write('main content')
            with open('./Pipfile.lock', 'w') as f:
                f.write("""
                {
                    "_meta": {
                        "sources": [
                            {
                                "name": "pypi",
                                "url": "https://pypi.python.org/simple",
                                "verify_ssl": true
                            },
                            {
                                "name": "external-index",
                                "url": "https://example.external-index.org/simple",
                                "verify_ssl": true
                            }
                        ]
                    },
                    "default": {
                        "package": {
                            "version": "==0.0.0"
                        },
                        "hash-package": {
                            "version": "==0.0.1",
                            "hash": "hash"
                        },
                        "hash-package2": {
                            "version": "==0.0.1",
                            "hashes": ["hash1", "hash2"]
                        },
                        "vcs-package": {
                            "git": "https://github.com/vcs/package.git",
                            "ref": "master",
                            "editable": true
                        }
                    }
                }
                """)
            with open('./1.egg', 'w') as f:
                f.write('1.egg content')
            with open('./2.egg', 'w') as f:
                f.write('2.egg content')
            files = self._deploy(req=req_name)

        reqs = set(files['requirements'][0].split('\n'))
        self.assertEqual(reqs, {
            '-i https://pypi.python.org/simple --extra-index-url https://example.external-index.org/simple',
            'package==0.0.0',
            'hash-package==0.0.1',
            'hash-package2==0.0.1',
            'git+https://github.com/vcs/package.git@master#egg=vcs-package'
            if sys.version_info < (3, 8)
            else 'vcs-package@ git+https://github.com/vcs/package.git@master'
        })

    def test_pipfile_names(self):
        self.pipfile_test('Pipfile')
        self.pipfile_test('Pipfile.lock')

    def test_pipfile_lock_missing(self):
        with self.runner.isolated_filesystem():
            with open('./main.egg', 'w') as f:
                f.write('main content')
            with open('./1.egg', 'w') as f:
                f.write('1.egg content')
            with open('./2.egg', 'w') as f:
                f.write('2.egg content')

            with self.assertRaises(ShubException) as cm:
                self._deploy(req='Pipfile')

            self.assertEqual(
                cm.exception.message,
                'Please lock your Pipfile before deploying',
            )

    def poetry_test(self, req_name):
        with self.runner.isolated_filesystem():
            with open('./main.egg', 'w') as f:
                f.write('main content')
            with open('./pyproject.toml', 'w') as f:
                f.write("""
                [tool.poetry]
                """)
            with open('./poetry.lock', 'w') as f:
                f.write("""
                [[package]]
                name = "package"
                version = "0.0.0"

                [[package]]
                name = "vcs-package"
                version = "0.0.1"

                [package.source]
                reference = "master"
                type = "git"
                url = "https://github.com/vcs/package.git"

                [[package]]
                name = "file-package"
                version = "0.0.1"

                [package.source]
                reference = ""
                type = "file"
                url = "/path/to/package.tar.gz"

                [[package]]
                name = "dir-package"
                version = "0.0.1"

                [package.source]
                reference = ""
                type = "directory"
                url = "/path/to/package"

                [metadata.hashes]
                package = ["hash"]
                vcs-package = ["hash1"]
                """)
            with open('./1.egg', 'w') as f:
                f.write('1.egg content')
            with open('./2.egg', 'w') as f:
                f.write('2.egg content')
            files = self._deploy(req=req_name)

        reqs = set(files['requirements'][0].split('\n'))
        self.assertEqual(reqs, {
            'package==0.0.0',
            'git+https://github.com/vcs/package.git@master#egg=vcs-package',
            '/path/to/package',
            '/path/to/package.tar.gz',
            '',
        })

    def test_poetry_names(self):
        self.poetry_test('pyproject.toml')

    def test_poetry_lock_missing(self):
        with self.runner.isolated_filesystem():
            with open('./pyproject.toml', 'w') as f:
                f.write("""
                [tool.poetry]
                """)
            with open('./main.egg', 'w') as f:
                f.write('main content')
            with open('./1.egg', 'w') as f:
                f.write('1.egg content')
            with open('./2.egg', 'w') as f:
                f.write('2.egg content')

            with self.assertRaises(ShubException) as cm:
                self._deploy(req='pyproject.toml')

            self.assertEqual(
                cm.exception.message,
                'Please make sure the poetry lock file is present',
            )


if __name__ == '__main__':
    unittest.main()
