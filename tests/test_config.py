import os
import shutil
import StringIO
import tempfile
import textwrap
import unittest
import ruamel.yaml as yaml

import mock

from click.testing import CliRunner

from shub.config import (get_target, get_target_conf, get_version,
                         load_shub_config, ShubConfig, Target,
                         update_yaml_dict)
from shub.exceptions import (BadParameterException, BadConfigException,
                             ConfigParseException, MissingAuthException,
                             NotFoundException)


VALID_YAML_CFG = """
    projects:
        shproj: 123
        externalproj: external/123
        notmeproj:
            id: 234
            apikey: otheruser
        advanced_prod:
            id: 456
            stack: hworker:v1.0.0
        advanced_dev:
            id: 457
            stack: dev
    endpoints:
        external: ext_endpoint
    apikeys:
        default: key
        otheruser: otherkey
    stacks:
        dev: scrapy:v1.1
    requirements_file: requirements.txt
    version: 1.0
"""


def _project_dict(proj_id, endpoint='default', extra=None):
    projd = {
        'id': proj_id,
        'endpoint': endpoint,
        'apikey': endpoint,
    }
    projd.update(extra or {})
    return projd


def _target(id, endpoint=None, apikey=None, stack=None,
            requirements_file='requirements.txt', version='1.0'):
    return Target(
        project_id=id,
        endpoint=endpoint or ShubConfig.DEFAULT_ENDPOINT,
        apikey=apikey,
        stack=stack,
        requirements_file=requirements_file,
        version=version,
    )


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
            'notmeproj': {
                'id': 234,
                'apikey': 'otheruser',
            },
            'advanced_prod': {
                'id': 456,
                'stack': 'hworker:v1.0.0',
            },
            'advanced_dev': {
                'id': 457,
                'stack': 'dev'
            },
        }
        self.assertEqual(projects, self.conf.projects)
        endpoints = {'external': 'ext_endpoint'}
        self.assertDictContainsSubset(endpoints, self.conf.endpoints)
        apikeys = {'default': 'key', 'otheruser': 'otherkey'}
        self.assertEqual(apikeys, self.conf.apikeys)
        stacks = {'dev': 'scrapy:v1.1'}
        self.assertEqual(stacks, self.conf.stacks)
        self.assertEqual('requirements.txt', self.conf.requirements_file)

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
                    url = http://app.scrapinghub.com/api/scrapyd/

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
            'otheruser': {
                'id': '333',
                'apikey': 'otheruser',
            },
            'otherurl': 'otherurl/444',
            'external': 'external/555',
        }
        expected_endpoints = {
            'default': ShubConfig.DEFAULT_ENDPOINT,
            'external': 'external_endpoint',
            'otherurl': 'http://app.scrapinghub.com/api/'
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

    def test_normalized_projects(self):
        expected_projects = {
            'shproj': _project_dict(123),
            'externalproj': _project_dict(123, 'external'),
            'notmeproj': _project_dict(234, extra={'apikey': 'otheruser'}),
            'advanced_prod': _project_dict(
                456, extra={'stack': 'hworker:v1.0.0'}),
            'advanced_dev': _project_dict(457, extra={'stack': 'dev'}),
        }
        self.assertEqual(self.conf.normalized_projects, expected_projects)

    def test_get_project(self):
        self.assertEqual(self.conf.get_project(123),
                         self.conf.get_project('shproj'))
        self.assertEqual(self.conf.get_project(456),
                         self.conf.get_project('advanced_prod'))
        self.assertEqual(self.conf.get_project(456),
                         self.conf.get_project('456'))
        self.assertEqual(self.conf.get_project('externalproj'),
                         self.conf.get_project('external/123'))

    def test_get_target_conf(self):
        self.assertEqual(
            self.conf.get_target_conf('shproj', auth_required=False),
            _target(123, apikey='key')
        )
        self.assertEqual(
            self.conf.get_target_conf('shproj', auth_required=True),
            self.conf.get_target_conf('shproj', auth_required=False),
        )
        with self.assertRaises(MissingAuthException):
            self.conf.get_target_conf('externalproj')
        self.assertEqual(
            self.conf.get_target_conf('externalproj', auth_required=False),
            _target(123, 'ext_endpoint')
        )
        self.assertEqual(
            self.conf.get_target_conf('notmeproj'),
            _target(234, apikey='otherkey'),
        )
        self.assertEqual(
            self.conf.get_target_conf('advanced_prod'),
            _target(456, apikey='key', stack='hworker:v1.0.0'),
        )
        self.assertEqual(
            self.conf.get_target_conf('advanced_dev'),
            _target(457, apikey='key', stack='scrapy:v1.1'),
        )

    def test_get_target_conf_custom_defaults(self):
        self.conf.load("""
            stacks:
              default: custom_default
        """)
        self.assertEqual(
            self.conf.get_target_conf('shproj'),
            _target(123, apikey='key', stack='custom_default')
        )
        self.assertEqual(
            self.conf.get_target_conf('advanced_prod'),
            _target(456, apikey='key', stack='hworker:v1.0.0'),
        )

    def test_get_target_conf_calls_get_project(self):
        t = _target(456, apikey='key', stack='hworker:v1.0.0')
        self.assertEqual(self.conf.get_target_conf('advanced_prod'), t)
        self.assertEqual(self.conf.get_target_conf(456), t)
        self.assertEqual(self.conf.get_target_conf('456'), t)
        self.assertEqual(self.conf.get_target_conf('default/456'), t)

    def test_get_undefined(self):
        self.assertEqual(
            self.conf.get_target_conf('99'),
            _target(99, apikey='key'),
        )
        self.assertEqual(
            self.conf.get_target_conf('external/99', auth_required=False),
            _target(99, 'ext_endpoint', None),
        )
        with self.assertRaises(NotFoundException):
            self.conf.get_target_conf('nonexisting_ep/33')

    def test_get_invalid(self):
        # Missing target and no default defined
        with self.assertRaises(BadParameterException):
            self.conf.get_target_conf('default')
        # Bad project ID on command line
        with self.assertRaises(BadParameterException):
            self.conf.get_target_conf('99a')
        # Bad project ID in scrapinghub.yml
        conf = self._get_conf_with_yml(
            """
            projects:
                invalid: 50a
                invalid2: 123/external
            """)
        with self.assertRaises(BadConfigException):
            conf.get_target_conf('invalid')
        with self.assertRaises(BadConfigException):
            conf.get_target_conf('invalid2')

    def test_apikey_always_str(self):
        # API keys should always be strings, even if they contain only digits
        self.conf.apikeys['default'] = 123
        self.assertEqual(
            self.conf.get_target_conf('shproj'),
            _target(123, apikey='123'),
        )

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
        get_target_conf('mytargetconf', auth_required=False)
        get_version()
        mock_lsh.return_value.get_target.assert_called_once_with(
            'mytarget', auth_required=False)
        mock_lsh.return_value.get_target_conf.assert_called_once_with(
            'mytargetconf', auth_required=False)
        mock_lsh.return_value.get_version.assert_called_once_with()
