#!/usr/bin/env python
# coding=utf-8


from __future__ import absolute_import
import json
import os
import stat
import sys
import unittest
import textwrap
import time

import click
import yaml

from click.testing import CliRunner
from collections import deque
from mock import Mock, MagicMock, patch
from scrapinghub import APIError

from shub import utils
from shub.config import ShubConfig
from shub.exceptions import (
    BadParameterException, InvalidAuthException, MissingAuthException,
    NotFoundException, RemoteErrorException, SubcommandException
)

from .utils import AssertInvokeRaisesMixin, mock_conf, mock_lazy_import


class UtilsTest(AssertInvokeRaisesMixin, unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    @patch('shub.utils.sys.frozen', new=True, create=True)
    @patch('shub.utils.find_exe', return_value='/my/python')
    def test_patch_sys_executable(self, mock_find_exe):
        original_exe = sys.executable
        with patch('shub.utils.sys.frozen', new=False):
            with utils.patch_sys_executable():
                self.assertEqual(sys.executable, original_exe)
        with utils.patch_sys_executable():
            self.assertEqual(sys.executable, '/my/python')
        # Make sure we properly cleaned up after ourselves
        self.assertEqual(sys.executable, original_exe)
        mock_find_exe.side_effect = NotFoundException
        with self.assertRaises(NotFoundException):
            with utils.patch_sys_executable():
                pass

    @patch('shub.utils.find_executable')
    def test_find_exe(self, mock_fe):
        mock_fe.return_value = '/usr/bin/python'
        self.assertEqual(utils.find_exe('python'), '/usr/bin/python')
        mock_fe.return_value = None
        with self.assertRaises(NotFoundException):
            utils.find_exe('python')

    def test_run_cmd_captures_stderr(self):
        cmd = [
            'python', '-c',
            # The next two lines are ONE list element (no comma)
            'from __future__ import print_function; import sys; '
            'print("Hello", file=sys.stderr)',
        ]
        self.assertEqual(utils.run_cmd(cmd), '')
        with self.assertRaisesRegexp(SubcommandException, 'STDERR[\s-]+Hello'):
            cmd[-1] += '; sys.exit(99)'
            utils.run_cmd(cmd)

    def test_pwd_git_version_without_git(self):
        # Change into test dir to make sure we're within a repo
        os.chdir(os.path.dirname(__file__))
        self.assertIsNotNone(utils.pwd_git_version())
        with patch('shub.utils.find_executable', return_value=None):
            self.assertIsNone(utils.pwd_git_version())

    @patch('shub.utils.pwd_git_version', return_value='ver_GIT')
    @patch('shub.utils.pwd_hg_version', return_value='ver_HG')
    @patch('shub.utils.pwd_bzr_version', return_value='ver_BZR')
    @patch('shub.utils.time.time', return_value=101)
    def test_pwd_version(self, mock_time, mock_bzr, mock_hg, mock_git):
        self.assertEqual(utils.pwd_version(), 'ver_GIT')
        mock_git.return_value = None
        self.assertEqual(utils.pwd_version(), 'ver_HG')
        mock_hg.return_value = None
        self.assertEqual(utils.pwd_version(), 'ver_BZR')
        mock_bzr.return_value = None
        with self.runner.isolated_filesystem():
            with open('setup.py', 'w') as f:
                f.write("from setuptools import setup\n")
                f.write("setup(version='1.0')")
            self.assertEqual(utils.pwd_version(), '1.0')
            setup_version = (
                'Building lxml version 3.4.4.'
                '\nBuilding without Cython.'
                '\nUsing build configuration of libxslt 1.1.28'
                '\n3.4.4'
            )
            with patch('shub.utils.run_python', return_value=setup_version):
                self.assertEqual(utils.pwd_version(), '3.4.4')
            os.mkdir('subdir')
            os.chdir('subdir')
            self.assertEqual(utils.pwd_version(), '101')
            open('../scrapy.cfg', 'w').close()
            self.assertEqual(utils.pwd_version(), '1.0')

    @patch('shub.utils.pwd_git_version')
    def test_pwd_version_clean(self, mock_git):
        mock_git.return_value = 'vers_1'
        self.assertEqual(utils.pwd_version(), 'vers_1')
        mock_git.return_value = 've  rs _ 2'
        self.assertEqual(utils.pwd_version(), 'vers_2')
        mock_git.return_value = 'vers -3_1:1'
        self.assertEqual(utils.pwd_version(), 'vers-3_11')
        mock_git.return_value = 'vers -4_1!$@%#&$()2'
        self.assertEqual(utils.pwd_version(), 'vers-4_12')

    def test_get_job_specs(self):
        conf = mock_conf(self)

        def _test_specs(job, expected_job_id, expected_endpoint):
            self.assertEqual(
                utils.get_job_specs(job),
                (expected_job_id, conf.get_apikey(expected_endpoint)),
            )
        _test_specs('10/20/30', '10/20/30', 'default')
        _test_specs('2/3', '1/2/3', 'default')
        _test_specs('default/2/3', '1/2/3', 'default')
        _test_specs('prod/2/3', '2/2/3', 'default')
        _test_specs('vagrant/2/3', '3/2/3', 'vagrant')
        _test_specs(
            'https://app.scrapinghub.com/p/7389/259/1/#/log/line/0',
            '7389/259/1',
            'default',
        )
        _test_specs(
            'https://app.scrapinghub.com/p/7389/job/259/1/',
            '7389/259/1',
            'default',
        )

    def test_get_job_specs_validates_jobid(self):
        invalid_job_ids = ['/1/1', '123', '1/2/a', '1//']
        for job_id in invalid_job_ids:
            with self.assertRaises(BadParameterException):
                utils.get_job_specs(job_id)

    @patch('scrapinghub.HubstorageClient', autospec=True)
    def test_get_job(self, mock_HSC):
        class MockJob(object):
            metadata = {'some': 'val'}
        mockjob = MockJob()
        mock_HSC.return_value.get_job.return_value = mockjob
        conf = mock_conf(self)

        self.assertIs(utils.get_job('1/1/1'), mockjob)
        mock_HSC.assert_called_once_with(auth=conf.apikeys['default'])

        with self.assertRaises(BadParameterException):
            utils.get_job('1/1/')

        # Non-existent job
        mockjob.metadata = None
        with self.assertRaises(NotFoundException):
            utils.get_job('1/1/1')

    def test_is_deploy_successful(self):
        # no results
        last_logs = deque(maxlen=5)
        assert not utils._is_deploy_successful(last_logs)
        # missing or incorrect data
        last_logs.append("")
        assert not utils._is_deploy_successful(last_logs)
        last_logs.append("abcdef")
        assert not utils._is_deploy_successful(last_logs)
        last_logs.append('{"field":"wrong"}')
        assert not utils._is_deploy_successful(last_logs)
        # error status
        last_logs.append('{"status":"error"}')
        assert not utils._is_deploy_successful(last_logs)
        # successful status
        last_logs.append('{"status":"ok"}')
        assert utils._is_deploy_successful(last_logs)
        last_logs.append('{"field":"value","status":"ok"}')
        assert utils._is_deploy_successful(last_logs)
        # more complex python expression
        last_logs.append('{"status":"ok", "project": 1111112, '
                         '"version": "1234-master", "spiders": 3}')
        assert utils._is_deploy_successful(last_logs)

    def test_job_live(self):
        job = MagicMock()
        job._metadata_updated = time.time()
        for live_value in ('pending', 'running'):
            job.metadata.__getitem__.return_value = live_value
            self.assertTrue(utils.job_live(job))
        for dead_value in ('finished', 'deleted'):
            job.metadata.__getitem__.return_value = dead_value
            self.assertFalse(utils.job_live(job))

    def test_job_live_updates_metadata(self):
        job = MagicMock(spec=['metadata'])
        with patch('shub.utils.time.time') as mock_time:
            mock_time.return_value = 0
            utils.job_live(job)
            mock_time.return_value = 10
            utils.job_live(job, refresh_meta_after=20)
            self.assertFalse(job.metadata.expire.called)
            utils.job_live(job, refresh_meta_after=5)
            self.assertTrue(job.metadata.expire.called)
            job.metadata.expire.reset_mock()
            utils.job_live(job, refresh_meta_after=5)
            self.assertFalse(job.metadata.expire.called)

    @patch('shub.utils.time.sleep')
    def test_job_resource_iter(self, mock_sleep):
        job = MagicMock(spec=['key', 'metadata', 'resource'])
        job.key = 'jobkey'
        job.metadata = {'state': 'running'}

        def make_items(iterable):
            return [json.dumps({'_key': x}) for x in iterable]

        def magic_iter(*args, **kwargs):
            """
            Return two different iterators on the first two calls, set job's
            state to 'finished' after the second call.
            """
            if magic_iter.stage == 0:
                if 'startafter' in kwargs:
                    self.assertEqual(kwargs['startafter'], None)
                magic_iter.stage = 1
                return iter(make_items([1, 2, 3]))
            elif magic_iter.stage == 1:
                self.assertEqual(kwargs['startafter'], 3)
                magic_iter.stage = 0
                job.metadata = {'state': 'finished'}
                return iter(make_items([4, 5, 6]))
            elif magic_iter.stage == 2:
                self.assertEqual(kwargs['startafter'], 'jobkey/996')
                return iter([])


        def jri_result(follow, tail=None):
            return list(utils.job_resource_iter(
                job,
                job.resource,
                follow=follow,
                tail=tail,
                output_json=True,
            ))

        job.resource.iter_json = magic_iter

        magic_iter.stage = 0
        self.assertEqual(jri_result(False), make_items([1, 2, 3]))
        self.assertFalse(mock_sleep.called)

        magic_iter.stage = 0
        self.assertEqual(jri_result(True), make_items([1, 2, 3, 4, 5, 6]))
        self.assertTrue(mock_sleep.called)

        magic_iter.stage = 0
        job.metadata = {'state': 'finished'}
        self.assertEqual(jri_result(True), make_items([1, 2, 3]))

        magic_iter.stage = 2
        job.resource.stats.return_value = {'totals': {'input_values': 1000}}
        self.assertEqual(jri_result(True, tail=3), [])

    @patch('requests.get', autospec=True)
    def test_latest_github_release(self, mock_get):
        with self.runner.isolated_filesystem():
            mock_get.return_value.json.return_value = {'key': 'value'}
            self.assertDictContainsSubset(
                {'key': 'value'},
                utils.latest_github_release(cache='./cache.txt'),
            )
            mock_get.return_value.json.return_value = {'key': 'newvalue'}
            self.assertDictContainsSubset(
                {'key': 'value'},
                utils.latest_github_release(cache='./cache.txt'),
            )
            self.assertDictContainsSubset(
                {'key': 'newvalue'},
                utils.latest_github_release(force_update=True,
                                            cache='./cache.txt'),
            )
            # Garbage in cache
            mock_get.return_value.json.return_value = {'key': 'value'}
            with open('./cache.txt', 'w') as f:
                f.write('abc')
            self.assertDictContainsSubset(
                {'key': 'value'},
                utils.latest_github_release(cache='./cache.txt'),
            )
            mock_get.return_value.json.return_value = {'key': 'newvalue'}
            self.assertDictContainsSubset(
                {'key': 'value'},
                utils.latest_github_release(cache='./cache.txt'),
            )
            # Readonly cache file
            mock_get.return_value.json.return_value = {'key': 'value'}
            with open('./cache.txt', 'w') as f:
                f.write('abc')
            os.chmod('./cache.txt', stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            self.assertDictContainsSubset(
                {'key': 'value'},
                utils.latest_github_release(cache='./cache.txt'),
            )
            mock_get.return_value.json.return_value = {'key': 'newvalue'}
            self.assertDictContainsSubset(
                {'key': 'newvalue'},
                utils.latest_github_release(cache='./cache.txt'),
            )
            with open('./cache.txt', 'r') as f:
                self.assertEqual(f.read(), 'abc')

    @patch('shub.utils.latest_github_release', autospec=True)
    @patch('shub.utils.shub.__version__', new='1.5.0')
    def test_update_available(self, mock_lgr):
        class MockException(Exception):
            pass
        mock_lgr.return_value = {'name': 'v1.4.0', 'html_url': 'link'}
        self.assertIsNone(utils.update_available())
        mock_lgr.return_value['name'] = 'v1.5.0'
        self.assertIsNone(utils.update_available())
        mock_lgr.return_value['name'] = 'v1.5.1'
        self.assertEqual(utils.update_available(), 'link')
        mock_lgr.return_value['name'] = 'v1.6.1'
        self.assertEqual(utils.update_available(), 'link')
        mock_lgr.return_value['name'] = 'v2.0.0'
        self.assertEqual(utils.update_available(), 'link')
        mock_lgr.return_value = {'error': 'unavailable'}
        self.assertIsNone(utils.update_available())
        mock_lgr.return_value = None
        self.assertIsNone(utils.update_available())
        mock_lgr.side_effect = MockException
        self.assertIsNone(utils.update_available())
        with self.assertRaises(MockException):
            utils.update_available(silent_fail=False)

    @mock_lazy_import('pip', autospec=True)
    def test_download_from_pypi(self, mock_pip):
        def _call(*args, **kwargs):
            utils.download_from_pypi(*args, **kwargs)
            return mock_pip.main.call_args[0][0]

        with self.assertRaises(ValueError):
            utils.download_from_pypi('tmpdir')
        with self.assertRaises(ValueError):
            utils.download_from_pypi('tmpdir', pkg='shub', reqfile='req.txt')
        self.assertFalse(mock_pip.main.called)

        # 1.0 (Ubuntu Precise)
        del mock_pip.__version__
        pipargs = _call('tmpdir', pkg='shub')
        self.assertNotIn('--no-use-wheel', pipargs)

        # 1.5.4 (Ubuntu Trusty)
        mock_pip.__version__ = '1.5.4'
        pipargs = _call('tmpdir', pkg='shub', extra_args=['--x'])
        self.assertEqual(pipargs[0], 'install')
        for expected_arg in ['--no-use-wheel', '--no-deps', 'shub', '--x']:
            self.assertIn(expected_arg, pipargs)
        # Make sure list contains '-d' followed by 'tmpdir'
        self.assertEqual(pipargs.index('-d') + 1, pipargs.index('tmpdir'))
        pipargs = _call('tmpdir', reqfile='req.txt')
        self.assertEqual(pipargs.index('-r') + 1, pipargs.index('req.txt'))

        # Replace deprecated commands in newer versions
        mock_pip.__version__ = '7.1.2.dev0'
        pipargs = _call('tmpdir', pkg='shub')
        self.assertEqual(pipargs[0], 'install')
        self.assertIn('--no-binary=:all:', pipargs)
        mock_pip.__version__ = '8.0.2'
        pipargs = _call('tmpdir', pkg='shub')
        self.assertEqual(pipargs[0], 'download')
        self.assertIn('--no-binary=:all:', pipargs)

    def test_echo_short_log_if_deployed(self):
        log_file = Mock(delete=None)
        last_logs = ["last log line"]

        deployed = True
        for verbose in [True, False]:
            utils.echo_short_log_if_deployed(
                deployed, last_logs, log_file, verbose)
            self.assertEqual(None, log_file.delete)

        deployed = False
        for verbose in [True, False]:
            utils.echo_short_log_if_deployed(
                deployed, last_logs, log_file, verbose)
            self.assertEqual(False, log_file.delete)

    def test_write_and_echo_logs(self):
        last_logs = []
        rsp = Mock()
        rsp.iter_lines = Mock(return_value=iter([b"line1", b"line2"]))
        self.assertRaises(RemoteErrorException,
            utils.write_and_echo_logs,
            keep_log=True, last_logs=last_logs,
            rsp=rsp, verbose=True)
        self.assertEqual(last_logs, [b"line1", b"line2"])
        last_logs = []

        rsp.iter_lines = Mock(return_value=iter(
            [b"line1", b'{"status":"ok","fieldK":"fieldV"}']))
        utils.write_and_echo_logs(keep_log=True, last_logs=last_logs,
                                  rsp=rsp, verbose=True)
        self.assertEqual(last_logs, [
            b"line1", b'{"status":"ok","fieldK":"fieldV"}'])

    def test_update_yaml_dict(self):
        YAML_BEFORE = textwrap.dedent("""\
            a:
              unrelated: dict
            b:
              key1: val1
              key2: val2
        """)
        DICT_EXPECTED = {
            'a': {'unrelated': 'dict'},
            'b': {'key1': 'newval1', 'key2': 'val2', 'key3': 'val3'}
        }
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open('conf.yml', 'w') as f:
                f.write(YAML_BEFORE)
            with utils.update_yaml_dict('conf.yml') as conf:
                conf['b']['key1'] = 'newval1'
                conf['b']['key3'] = 'val3'
            with open('conf.yml', 'r') as f:
                self.assertEqual(yaml.safe_load(f), DICT_EXPECTED)
                f.seek(0)
                self.assertIn("key1: newval1", f.read())

    def test_update_yaml_dict_handles_file_errors(self):
        with CliRunner().isolated_filesystem():
            self.assertFalse(os.path.isfile('didnt_exist.yml'))
            with utils.update_yaml_dict('didnt_exist.yml') as conf:
                pass
            self.assertTrue(os.path.isfile('didnt_exist.yml'))

            os.mkdir('a_directory')
            with self.assertRaises(IOError):
                with utils.update_yaml_dict('a_directory'):
                    pass

    @patch('shub.config.GLOBAL_SCRAPINGHUB_YML_PATH', 'global.yml')
    def test_update_yaml_dict_uses_global_by_default(self):
        @click.command()
        def call_update_yaml_dict():
            with utils.update_yaml_dict():
                pass

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(call_update_yaml_dict)
        assert 'deprecated' in result.output

    @patch('scrapinghub.Connection')
    def test_has_project_access(self, mock_conn):
        mock_conn.return_value.project_ids.side_effect = APIError(
            'Authentication failed')
        with self.assertRaises(InvalidAuthException):
            utils.has_project_access(12345, 'mock_endpoint', 'abcdef')
        mock_conn.return_value.project_ids.side_effect = APIError(
            'Random error')
        with self.assertRaises(RemoteErrorException):
            utils.has_project_access(12345, 'mock_endpoint', 'abcdef')

    def test_get_project_dir(self):
        with CliRunner().isolated_filesystem() as basepath:
            os.makedirs('a/b/c')
            os.chdir('a/b/c')
            with self.assertRaises(NotFoundException):
                utils.get_project_dir()
            open(os.path.join(basepath, 'Dockerfile'), 'w').close()
            self.assertEqual(utils.get_project_dir(), basepath)
            # scrapy.cfg takes precedence over Dockerfile
            open(os.path.join(basepath, 'a', 'scrapy.cfg'), 'w').close()
            self.assertEqual(
                utils.get_project_dir(),
                os.path.join(basepath, 'a'))
            # scrapinghub.yml takes precedence over both
            open(os.path.join(basepath, 'a', 'b', 'scrapinghub.yml'), 'w'
                 ).close()
            self.assertEqual(
                utils.get_project_dir(),
                os.path.join(basepath, 'a', 'b'))


class OnboardingWizardTestCase(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.has_project_access = True

    @patch('shub.utils.has_project_access')
    def _test_wizard(self, mock_project_access, conf=None, target='default',
                     image=None, sh_yml=None, scrapy_cfg=True,
                     dockerfile=False, **kwargs):
        if not conf:
            conf = ShubConfig()
            conf.apikeys = {'default': 'abcdef'}
        mock_project_access.return_value = self.has_project_access

        @click.command()
        def call_wizard():
            utils.create_scrapinghub_yml_wizard(
                conf, target=target, image=image)

        with self.runner.isolated_filesystem():
            if scrapy_cfg:
                open('scrapy.cfg', 'w').close()
            if dockerfile:
                open('Dockerfile', 'w').close()
            if sh_yml:
                with open('scrapinghub.yml', 'w') as f:
                    f.write(sh_yml)
                conf.load_file('scrapinghub.yml')
            result = self.runner.invoke(call_wizard, **kwargs)
            if os.path.exists('scrapinghub.yml'):
                with open('scrapinghub.yml', 'r') as f:
                    sh_yml = yaml.safe_load(f.read())
            else:
                sh_yml = None
            return result, conf, sh_yml

    def test_outside_of_project(self):
        result, _, sh_yml = self._test_wizard(scrapy_cfg=False)
        assert result.exit_code == NotFoundException.exit_code
        assert sh_yml is None

    def test_not_logged_in(self):
        conf = ShubConfig()
        result, _, sh_yml = self._test_wizard(conf=conf)
        assert result.exit_code == MissingAuthException.exit_code
        assert sh_yml is None

    def test_scrapy_project(self):
        result, conf, sh_yml = self._test_wizard(input='12345\n')
        assert result.exit_code == 0
        assert conf.projects == {'default': 12345}
        assert sh_yml == {'project': 12345}

    def test_custom_project(self):
        result, conf, sh_yml = self._test_wizard(
            scrapy_cfg=False, dockerfile=True, input='12345\n\n')
        assert result.exit_code == 0
        assert conf.projects == {'default': 12345}
        assert conf.images == {'default': True}
        assert sh_yml == {'project': 12345, 'image': True}

    def test_custom_repository(self):
        result, conf, sh_yml = self._test_wizard(
            scrapy_cfg=False, dockerfile=True, input='12345\nrepo\n')
        assert result.exit_code == 0
        assert conf.images == {'default': 'repo'}
        assert sh_yml == {'project': 12345, 'image': 'repo'}

    def test_ambiguous_project_not_custom(self):
        result, conf, sh_yml = self._test_wizard(
            scrapy_cfg=True, dockerfile=True, input='12345\nn\n')
        assert result.exit_code == 0
        assert conf.projects == {'default': 12345}
        assert not conf.images
        assert sh_yml == {'project': 12345}

    def test_ambiguous_project_custom(self):
        result, conf, sh_yml = self._test_wizard(
            scrapy_cfg=True, dockerfile=True, input='12345\n\n\n')
        assert result.exit_code == 0
        assert conf.projects == {'default': 12345}
        assert conf.images == {'default': True}
        assert sh_yml == {'project': 12345, 'image': True}

    def test_never_ask_for_repository_when_image_false(self):
        result, conf, _ = self._test_wizard(
            image=False, scrapy_cfg=False, dockerfile=True, input='12345\n')
        assert result.exit_code == 0
        assert 'repository' not in result.output
        assert not conf.images

    def test_always_ask_for_repository_when_image_true(self):
        result, conf, sh_yml = self._test_wizard(
            image=True, input='12345\nrepo\n')
        assert result.exit_code == 0
        assert conf.images == {'default': 'repo'}
        assert sh_yml == {'project': 12345, 'image': 'repo'}

    def test_skip_on_existing_scrapinghub_yml_and_not_image(self):
        original_sh_yml = 'project: 12345\n'
        result, conf, sh_yml = self._test_wizard(sh_yml=original_sh_yml)
        assert result.exit_code == 0
        assert not result.output
        assert not conf.images
        assert sh_yml == {'project': 12345}

    def test_add_image_for_existing_default_target(self):
        original_sh_yml = 'projects:\n  default: 12345\n  prod: 33333\n'
        result, conf, sh_yml = self._test_wizard(
            image=True, sh_yml=original_sh_yml, input='\n')
        assert result.exit_code == 0
        assert conf.images == {'default': True}
        assert sh_yml == {
            'projects': {'default': 12345, 'prod': 33333},
            'image': True
        }

    def test_add_image_for_existing_nondefault_target(self):
        original_sh_yml = 'projects:\n  default: 12345\n  prod: 33333\n'
        result, conf, sh_yml = self._test_wizard(
            target='prod', image=True, sh_yml=original_sh_yml, input='\n')
        assert result.exit_code == 0
        assert not conf.images
        assert sh_yml == {
            'projects': {
                'default': 12345,
                'prod': {
                    'id': 33333,
                    'image': True,
                },
            },
        }

    def test_skip_for_already_defined_default_image(self):
        original_sh_yml = 'project: 12345\nimage: true\n'
        result, conf, sh_yml = self._test_wizard(
            image=True, sh_yml=original_sh_yml)
        assert result.exit_code == 0
        assert not result.output

    def test_skip_for_already_defined_nondefault_image(self):
        original_sh_yml = textwrap.dedent("""\
            projects:
              default: 12345
              prod:
                id: 33333
                image: true\
            """)
        result, conf, sh_yml = self._test_wizard(
            target='prod', image=True, sh_yml=original_sh_yml)
        assert result.exit_code == 0
        assert not result.output

    def test_scrapy_project_with_numeric_target(self):
        result, conf, sh_yml = self._test_wizard(target='12345')
        assert result.exit_code == 0
        assert conf.projects == {'default': 12345}
        assert sh_yml == {'project': 12345}

    def test_custom_project_with_numeric_target(self):
        result, conf, sh_yml = self._test_wizard(
            target='12345', scrapy_cfg=False, dockerfile=True, input='repo\n')
        assert result.exit_code == 0
        assert conf.projects == {'default': 12345}
        assert conf.images == {'default': 'repo'}
        assert sh_yml == {'project': 12345, 'image': 'repo'}

    def test_dont_leak_global_config(self):
        conf = ShubConfig()
        conf.projects = {'prod': 33333}
        conf.apikeys = {'default': 'abc'}
        result, conf, sh_yml = self._test_wizard(conf=conf, input='12345\n')
        assert result.exit_code == 0
        assert conf.projects == {'default': 12345, 'prod': 33333}
        assert conf.apikeys == {'default': 'abc'}
        assert sh_yml == {'project': 12345}

    def test_dont_leak_global_config_on_image(self):
        conf = ShubConfig()
        conf.projects = {'prod': 33333}
        conf.apikeys = {'default': 'abc'}
        result, conf, sh_yml = self._test_wizard(
            conf=conf, scrapy_cfg=False, dockerfile=True,
            input='12345\nrepo\n')
        assert result.exit_code == 0
        assert conf.projects == {'default': 12345, 'prod': 33333}
        assert conf.apikeys == {'default': 'abc'}
        assert conf.images == {'default': 'repo'}
        assert sh_yml == {'project': 12345, 'image': 'repo'}


if __name__ == '__main__':
    unittest.main()
