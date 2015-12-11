import os
import shutil
import StringIO
import tempfile
import textwrap
import unittest

import mock

from click import ClickException
from click.testing import CliRunner

from shub.config import load_shub_config, ShubConfig, update_config


VALID_YAML_CFG = """
    projects:
        shproj: 123
        externalproj: external/123
        invalid: 50a
        invalid2: 123/external
    endpoints:
        external: ext_endpoint
    apikeys:
        default: key
    versions:
        shproj: 2.0
"""


class ShubConfigTest(unittest.TestCase):

    def _get_conf_with_yml(self, yml):
        conf = ShubConfig()
        conf.load(StringIO.StringIO(textwrap.dedent(yml)))
        return conf

    def setUp(self):
        self.conf = self._get_conf_with_yml(VALID_YAML_CFG)

    def test_init_sets_default(self):
        conf = ShubConfig()
        self.assertIn('default', conf.endpoints)

    def test_load(self):
        projects = {
            'shproj': 123,
            'externalproj': 'external/123',
            'invalid': '50a',
            'invalid2': '123/external',
        }
        self.assertEqual(projects, self.conf.projects)
        endpoints = {'external': 'ext_endpoint'}
        self.assertDictContainsSubset(endpoints, self.conf.endpoints)
        apikeys = {'default': 'key'}
        self.assertEqual(apikeys, self.conf.apikeys)

    def test_load_partial(self):
        yml = """
            endpoints:
                external: ext_endpoint
            extra:
                not related to ShubConfig
        """
        conf = self._get_conf_with_yml(yml)
        endpoints = {'external': 'ext_endpoint'}
        self.assertDictContainsSubset(endpoints, conf.endpoints)
        self.assertEqual(conf.projects, {})
        self.assertEqual(conf.apikeys, {})

    def test_load_malformed(self):
        # Invalid YAML
        yml = """
            endpoints
                external: ext_endpoint
            apikeys:
                default: key
        """
        with self.assertRaises(ClickException):
            self._get_conf_with_yml(yml)
        # Valid YAML but not dictionary-like
        yml = """
            endpoints
                external: ext_endpoint
        """
        with self.assertRaises(ClickException):
            self._get_conf_with_yml(yml)

    def test_load_file(self):
        tmpdir = tempfile.mkdtemp()
        tmpfilepath = os.path.join(tmpdir, 'scrapinghub.yml')
        with open(tmpfilepath, 'w') as f:
            f.write(textwrap.dedent(
                """
                apikeys:
                    external: ext_endpoint
                """
            ))
        conf = ShubConfig()
        conf.load_file(tmpfilepath)
        shutil.rmtree(tmpdir)
        self.assertEqual({'external': 'ext_endpoint'}, conf.apikeys)

    def test_get_target(self):
        with self.assertRaises(ClickException):
            self.conf.get_target('externalproj')
        self.assertEqual(
            self.conf.get_target('externalproj', auth_required=False),
            (123, 'ext_endpoint', None)
        )
        self.assertEqual(
            self.conf.get_target('shproj', auth_required=True),
            self.conf.get_target('shproj', auth_required=False),
        )

    def test_get_undefined(self):
        self.assertEqual(
            self.conf.get_target('99'),
            (99, self.conf.endpoints['default'], 'key'),
        )
        self.assertEqual(
            self.conf.get_target('external/99', auth_required=False),
            (99, 'ext_endpoint', None),
        )
        with self.assertRaises(ClickException):
            self.conf.get_target('99a')

    def test_get_invalid(self):
        with self.assertRaises(ClickException):
            self.conf.get_target('invalid')
        with self.assertRaises(ClickException):
            self.conf.get_target('invalid2')

    def test_get_project_id(self):
        self.assertEqual(self.conf.get_project_id('shproj'), 123)
        self.assertEqual(self.conf.get_project_id('externalproj'), 123)

    def test_get_endpoint(self):
        self.assertEqual(
            self.conf.get_endpoint('shproj'),
            ShubConfig().endpoints['default'],
        )
        self.assertEqual(
            self.conf.get_endpoint('externalproj'),
            'ext_endpoint',
        )

    def test_get_apikey(self):
        self.assertEqual(self.conf.get_apikey('shproj'), 'key')
        with self.assertRaises(ClickException):
            self.conf.get_apikey('externalproj', required=True)
        self.assertEqual(
            self.conf.get_apikey('externalproj', required=False),
            None,
        )

    def test_get_version(self):
        self.assertEqual(self.conf.get_version('shproj'), '2.0')
        with mock.patch('shub.config.time.time', return_value=101):
            self.assertEqual(self.conf.get_version('externalproj'), '101')
            self.assertEqual(self.conf.get_version('undef'), '101')
            self.assertEqual(self.conf.get_version('undef', '2.0'), '2.0')
        with mock.patch('shub.config.pwd_hg_version', return_value='ver_HG'):
            self.assertEqual(self.conf.get_version('undef', 'HG'), 'ver_HG')
        with mock.patch('shub.config.pwd_git_version', return_value='ver_GIT'):
            self.assertEqual(self.conf.get_version('undef', 'GIT'), 'ver_GIT')


LOCAL_SCRAPINGHUB_YML = """
    projects:
        localextproj: external/123
    endpoints:
        external: local_ext_endpoint
    apikeys:
        external: key_ext
"""


class LoadShubConfigTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.globalpath = os.path.join(self.tmpdir, '.scrapinghub.yml')
        self.localpath = os.path.join(self.tmpdir, 'scrapinghub.yml')
        with open(self.globalpath, 'w') as f:
            f.write(VALID_YAML_CFG)
        with open(self.localpath, 'w') as f:
            f.write(LOCAL_SCRAPINGHUB_YML)
        self._old_dir = os.getcwd()
        os.chdir(self.tmpdir)

        self.patcher_gsy = mock.patch('shub.config._global_scrapinghub_yml')
        self.addCleanup(self.patcher_gsy.stop)
        self.mock_gsy = self.patcher_gsy.start()
        self.mock_gsy.return_value = self.globalpath

    def tearDown(self):
        os.chdir(self._old_dir)
        shutil.rmtree(self.tmpdir)

    def test_scrapinghub_ymls_read(self):
        conf = load_shub_config()
        self.assertEqual(conf.get_apikey('shproj'), 'key')
        self.assertEqual(
            conf.get_endpoint('externalproj'),
            'local_ext_endpoint',
        )
        self.assertEqual(conf.get_apikey('externalproj'), 'key_ext')

    def test_local_scrapinghub_yml_in_parent_dir(self):
        subsubdir = os.path.join(self.tmpdir, 'sub/sub')
        os.makedirs(subsubdir)
        os.chdir(subsubdir)
        conf = load_shub_config()
        self.assertEqual(conf.get_apikey('externalproj'), 'key_ext')

    def test_no_local_scrapinghub_yml(self):
        os.remove(self.localpath)
        conf = load_shub_config()
        self.assertEqual(conf.get_apikey('shproj'), 'key')
        with self.assertRaises(ClickException):
            conf.get_apikey('localextproj')

    def test_no_global_scrapinghub_yml(self):
        os.remove(self.globalpath)
        self.mock_gsy.return_value = None
        conf = load_shub_config()
        with self.assertRaises(ClickException):
            conf.get_apikey('shproj')
        self.assertEqual(conf.get_apikey('localextproj'), 'key_ext')

    def test_envvar_precedence(self):
        _old_environ = dict(os.environ)
        os.environ['SHUB_APIKEY'] = 'key_env'
        conf = load_shub_config()
        self.assertEqual(conf.get_apikey('shproj'), 'key_env')
        os.environ.clear()
        os.environ.update(_old_environ)

    def test_fallback_to_scrapy_cfg(self):
        scrapycfg = """
            [deploy]
            project = 222
            url = scrapycfg_endpoint

            [deploy:ext2]
            url = ext2_endpoint
            project = 333
            username = ext2_key
            version = ext2_ver
        """
        with open(os.path.join(self.tmpdir, 'scrapy.cfg'), 'w') as f:
            f.write(textwrap.dedent(scrapycfg))
        conf = load_shub_config()
        with self.assertRaises(ClickException):
            conf.get_target('ext2')
        os.remove(self.localpath)
        conf = load_shub_config()
        self.assertEqual(
            conf.get_target('default'),
            (222, 'scrapycfg_endpoint', 'key'),
        )
        self.assertEqual(
            conf.get_target('ext2'),
            (333, 'ext2_endpoint', 'ext2_key'),
        )
        self.assertEqual(conf.get_version('ext2'), 'ext2_ver')


class UpdateConfigTest(unittest.TestCase):

    def test_update_config(self):
        YAML_BEFORE = textwrap.dedent("""\
            z_first:
              unrelated: dict
            a_second:
              key1: val1
              # some comment
              key2: val2
        """)
        YAML_EXPECTED = textwrap.dedent("""\
            z_first:
              unrelated: dict
            a_second:
              key1: newval1
              # some comment
              key2: val2
              key3: val3
        """)
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open('conf.yml', 'w') as f:
                f.write(YAML_BEFORE)
            with update_config('conf.yml') as conf:
                conf['a_second']['key1'] = 'newval1'
                conf['a_second']['key3'] = 'val3'
            with open('conf.yml', 'r') as f:
                self.assertEqual(f.read(), YAML_EXPECTED)
