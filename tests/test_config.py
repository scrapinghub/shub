import os
import shutil
import StringIO
import tempfile
import textwrap
import unittest
import ruamel.yaml as yaml

import mock

from click.testing import CliRunner

from shub.config import (get_target, get_version, load_shub_config, ShubConfig,
                         update_yaml_dict)
from shub.exceptions import (BadParameterException, BadConfigException,
                             ConfigParseException, MissingAuthException,
                             NotFoundException)


VALID_YAML_CFG = """
    projects:
        shproj: 123
        externalproj: external/123
        notmeproj: otheruser/123
        invalid: 50a
        invalid2: 123/external
    endpoints:
        external: ext_endpoint
    apikeys:
        default: key
        otheruser: otherkey
    stacks:
        shproj: "hworker:v1.0.0"
    requirements_file: scrapinghub-requirements.txt
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
        self.assertEqual(conf.version, 'AUTO')

    def test_load(self):
        projects = {
            'shproj': 123,
            'externalproj': 'external/123',
            'notmeproj': 'otheruser/123',
            'invalid': '50a',
            'invalid2': '123/external',
        }
        self.assertEqual(projects, self.conf.projects)
        endpoints = {'external': 'ext_endpoint'}
        self.assertDictContainsSubset(endpoints, self.conf.endpoints)
        apikeys = {'default': 'key', 'otheruser': 'otherkey'}
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
        # Assert no exception raised on empty file
        conf = self._get_conf_with_yml("")

    def test_load_malformed(self):
        # Invalid YAML
        yml = """
            endpoints
                external: ext_endpoint
            apikeys:
                default: key
        """
        with self.assertRaises(ConfigParseException):
            self._get_conf_with_yml(yml)
        # Valid YAML but not dictionary-like
        yml = """
            endpoints
                external: ext_endpoint
        """
        with self.assertRaises(ConfigParseException):
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

    def test_load_scrapycfg(self):
        tmpdir = tempfile.mkdtemp()
        tmpfilepath = os.path.join(tmpdir, 'scrapy.cfg')

        def _get_conf(scrapycfg_default_target):
            with open(tmpfilepath, 'w') as f:
                f.write(textwrap.dedent(scrapycfg_default_target))
                f.write(textwrap.dedent(
                    """
                    [deploy:prod]
                    project = 222

                    [deploy:otheruser]
                    project = 333
                    username = otherkey

                    [deploy:otherurl]
                    project = 444
                    url = http://dash.scrapinghub.com/api/scrapyd/

                    [deploy:external]
                    project = 555
                    url = external_endpoint
                    username = externalkey

                    [deploy:invalid_external]
                    project = non-numeric
                    url = external_endpoint
                    username = externalkey
                    """
                ))
            conf = ShubConfig()
            conf.load_scrapycfg([tmpfilepath])
            return conf

        expected_projects = {
            'prod': '222',
            'otheruser': 'otheruser/333',
            'otherurl': 'otherurl/444',
            'external': 'external/555',
        }
        expected_endpoints = {
            'default': ShubConfig.DEFAULT_ENDPOINT,
            'external': 'external_endpoint',
            'otherurl': 'http://dash.scrapinghub.com/api/'
        }
        expected_apikeys = {
            'otheruser': 'otherkey',
            'external': 'externalkey',
        }

        def _test_conf(scrapycfg_default_target):
            conf = _get_conf(scrapycfg_default_target)
            self.assertEqual(conf.projects, expected_projects)
            self.assertEqual(conf.endpoints, expected_endpoints)
            self.assertEqual(conf.apikeys, expected_apikeys)

        # Default with invalid project
        _test_conf(
            """
            [deploy]
            project = non-numeric
            """
        )

        # Default with valid project
        expected_projects['default'] = '111'
        _test_conf(
            """
            [deploy]
            project = 111
            """
        )

        # Default with URL
        del expected_projects['default']
        expected_endpoints['default'] = 'http://default_url'
        _test_conf(
            """
            [deploy]
            url = http://default_url
            """
        )

        # Default with key
        expected_endpoints['default'] = ShubConfig.DEFAULT_ENDPOINT
        expected_apikeys['default'] = 'key'
        expected_apikeys['otherurl'] = 'key'
        _test_conf(
            """
            [deploy]
            username = key
            """
        )

        shutil.rmtree(tmpdir)

    def test_save(self):
        tmpdir = tempfile.mkdtemp()
        tmpfilepath = os.path.join(tmpdir, 'saved_conf.yml')
        self.conf.save(tmpfilepath)
        with open(tmpfilepath, 'r') as f:
            self.assertEqual(yaml.load(f), yaml.load(VALID_YAML_CFG))
        shutil.rmtree(tmpdir)

    def test_get_target(self):
        with self.assertRaises(MissingAuthException):
            self.conf.get_target('externalproj')
        self.assertEqual(
            self.conf.get_target('externalproj', auth_required=False),
            (123, 'ext_endpoint', None)
        )
        self.assertEqual(
            self.conf.get_target('shproj', auth_required=True),
            self.conf.get_target('shproj', auth_required=False),
        )

    def test_get_stack(self):
        assert self.conf.get_stack('shproj') == 'hworker:v1.0.0'
        assert self.conf.get_targetconf('shproj').stack == 'hworker:v1.0.0'

    def test_requirements(self):
        assert self.conf.requirements_file == 'scrapinghub-requirements.txt'
        assert self.conf.get_targetconf('shproj').requirements_file == \
            'scrapinghub-requirements.txt'

    def test_get_undefined(self):
        self.assertEqual(
            self.conf.get_target('99'),
            (99, self.conf.endpoints['default'], 'key'),
        )
        self.assertEqual(
            self.conf.get_target('external/99', auth_required=False),
            (99, 'ext_endpoint', None),
        )

    def test_get_invalid(self):
        # Missing target and no default defined
        with self.assertRaises(BadParameterException):
            self.conf.get_target('default')
        # Bad project ID on command line
        with self.assertRaises(BadParameterException):
            self.conf.get_target('99a')
        # Bad project ID in scrapinghub.yml
        with self.assertRaises(BadConfigException):
            self.conf.get_target('invalid')
        with self.assertRaises(BadConfigException):
            self.conf.get_target('invalid2')

    def test_get_project_id(self):
        self.assertEqual(self.conf.get_project_id('shproj'), 123)
        self.assertEqual(self.conf.get_project_id('externalproj'), 123)
        self.assertEqual(self.conf.get_project_id('notmeproj'), 123)

    def test_get_endpoint(self):
        self.assertEqual(
            self.conf.get_endpoint('shproj'),
            ShubConfig.DEFAULT_ENDPOINT,
        )
        self.assertEqual(
            self.conf.get_endpoint('externalproj'),
            'ext_endpoint',
        )
        self.assertEqual(
            self.conf.get_endpoint('notmeproj'),
            ShubConfig.DEFAULT_ENDPOINT,
        )
        with self.assertRaises(NotFoundException):
            self.conf.get_endpoint('nonexisting_ep/33')

    def test_get_apikey(self):
        self.assertEqual(self.conf.get_apikey('shproj'), 'key')
        self.assertEqual(self.conf.get_apikey('notmeproj'), 'otherkey')
        with self.assertRaises(MissingAuthException):
            self.conf.get_apikey('externalproj', required=True)
        self.assertEqual(
            self.conf.get_apikey('externalproj', required=False),
            None,
        )
        # API keys should always be strings, even if they contain only digits
        self.conf.apikeys['default'] = 123
        self.assertEqual(self.conf.get_apikey('shproj'), '123')

    @mock.patch('shub.config.pwd_version', return_value='ver_AUTO')
    @mock.patch('shub.config.pwd_git_version', return_value='ver_GIT')
    @mock.patch('shub.config.pwd_hg_version', return_value='ver_HG')
    def test_get_version(self, mock_hg, mock_git, mock_ver):
        def _assert_version(version, expected):
            self.conf.version = version
            self.assertEqual(self.conf.get_version(), expected)
        _assert_version('GIT', 'ver_GIT')
        _assert_version('HG', 'ver_HG')
        _assert_version('somestring', 'somestring')
        _assert_version('', 'ver_AUTO')
        _assert_version('AUTO', 'ver_AUTO')


LOCAL_SCRAPINGHUB_YML = """
    projects:
        localextproj: external/123
    endpoints:
        external: local_ext_endpoint
    apikeys:
        external: key_ext
"""

GLOBAL_SCRAPY_CFG = textwrap.dedent("""
    [deploy]
    url = dotsc_endpoint
    username = dotsc_key

    [deploy:ext2]
    url = ext2_endpoint
    project = 333
    username = ext2_key
""")

NETRC = 'machine scrapinghub.com login netrc_key password ""'


class LoadShubConfigTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.globalpath = os.path.join(self.tmpdir, '.scrapinghub.yml')
        self.localpath = os.path.join(self.tmpdir, 'scrapinghub.yml')
        self.globalscrapycfgpath = os.path.join(self.tmpdir, '.scrapy.cfg')
        self.localscrapycfgpath = os.path.join(self.tmpdir, 'scrapy.cfg')
        self.netrcpath = os.path.join(self.tmpdir, '.netrc')
        with open(self.globalpath, 'w') as f:
            f.write(VALID_YAML_CFG)
        with open(self.localpath, 'w') as f:
            f.write(LOCAL_SCRAPINGHUB_YML)
        with open(self.globalscrapycfgpath, 'w') as f:
            f.write(GLOBAL_SCRAPY_CFG)
        with open(self.netrcpath, 'w') as f:
            f.write(NETRC)
        self._old_dir = os.getcwd()
        os.chdir(self.tmpdir)

        patcher_gsyp = mock.patch('shub.config.GLOBAL_SCRAPINGHUB_YML_PATH',
                                  new=self.globalpath)
        patcher_nrcp = mock.patch('shub.config.NETRC_PATH', new=self.netrcpath)
        patcher_gs = mock.patch('shub.config.get_sources',
                                return_value=[self.globalscrapycfgpath])
        self.addCleanup(patcher_gsyp.stop)
        self.addCleanup(patcher_nrcp.stop)
        self.addCleanup(patcher_gs.stop)
        patcher_gsyp.start()
        patcher_nrcp.start()
        patcher_gs.start()

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
        with self.assertRaises(BadParameterException):
            conf.get_project_id('ext2')

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
        with self.assertRaises(BadParameterException):
            conf.get_apikey('localextproj')

    def test_no_global_scrapinghub_yml(self):
        os.remove(self.globalpath)
        conf = load_shub_config()
        with self.assertRaises(BadParameterException):
            conf.get_apikey('shproj')
        self.assertEqual(conf.get_apikey('localextproj'), 'key_ext')

    def test_envvar_precedence(self):
        _old_environ = dict(os.environ)
        os.environ['SHUB_APIKEY'] = 'key_env'
        conf = load_shub_config()
        self.assertEqual(conf.get_apikey('shproj'), 'key_env')
        os.environ.clear()
        os.environ.update(_old_environ)

    def test_autocreate_empty_global_scrapinghub_yml(self):
        os.remove(self.globalpath)
        os.remove(self.globalscrapycfgpath)
        os.remove(self.netrcpath)
        load_shub_config()
        self.assertTrue(os.path.isfile(self.globalpath))
        with open(self.globalpath, 'r') as f:
            self.assertEqual(f.read(), "")

    def test_automigrate_to_global_scrapinghub_yml(self):
        def _check_conf():
            conf = load_shub_config()
            self.assertEqual(
                conf.get_target('123'),
                (123, 'dotsc_endpoint', 'netrc_key'),
            )
            self.assertEqual(conf.projects['ext2'], 'ext2/333')
            self.assertEqual(
                conf.get_target('ext2'),
                (333, 'ext2_endpoint', 'ext2_key'),
            )
        os.remove(self.globalpath)
        _check_conf()
        self.assertTrue(os.path.isfile(self.globalpath))
        os.remove(self.netrcpath)
        os.remove('.scrapy.cfg')
        _check_conf()

    def test_automigrate_project_scrapy_cfg(self):
        def _check_conf():
            conf = load_shub_config()
            self.assertEqual(
                conf.get_target('default'),
                (222, 'scrapycfg_endpoint/', 'key'),
            )
            self.assertEqual(
                conf.get_target('ext2'),
                (333, 'ext2_endpoint/', 'ext2_key'),
            )
            self.assertEqual(
                conf.get_target('ext3'),
                (333, 'scrapycfg_endpoint/', 'key'),
            )
            self.assertEqual(
                conf.get_target('ext4'),
                (444, 'scrapycfg_endpoint/', 'ext4_key'),
            )
            self.assertEqual(conf.get_version(), 'ext2_ver')
        scrapycfg = """
            [deploy]
            project = 222
            url = scrapycfg_endpoint/scrapyd/

            [deploy:ext2]
            url = ext2_endpoint/scrapyd/
            project = 333
            username = ext2_key
            version = ext2_ver

            [deploy:ext3]
            project = 333

            [deploy:ext4]
            project = 444
            username = ext4_key
        """
        with open(self.localscrapycfgpath, 'w') as f:
            f.write(textwrap.dedent(scrapycfg))
        os.mkdir('project')
        os.chdir('project')
        conf = load_shub_config()
        with self.assertRaises(BadParameterException):
            conf.get_target('ext2')
        os.remove(self.localpath)
        # Loaded from scrapy.cfg
        _check_conf()
        # Same config should now be loaded from scrapinghub.yml
        self.assertTrue(os.path.isfile(self.localpath))
        _check_conf()


class ConfigHelpersTest(unittest.TestCase):

    def test_update_yaml_dict(self):
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
            with update_yaml_dict('conf.yml') as conf:
                conf['a_second']['key1'] = 'newval1'
                conf['a_second']['key3'] = 'val3'
            with open('conf.yml', 'r') as f:
                self.assertEqual(f.read(), YAML_EXPECTED)

    @mock.patch('shub.config.load_shub_config')
    def test_get_target_version(self, mock_lsh):
        get_target('mytarget', auth_required=False)
        get_version()
        mock_lsh.return_value.get_target.assert_called_once_with(
            'mytarget', auth_required=False)
        mock_lsh.return_value.get_version.assert_called_once_with()
