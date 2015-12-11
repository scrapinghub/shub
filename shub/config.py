import contextlib
import os.path
import time

import click
from click import ClickException
import six
import ruamel.yaml as yaml

from shub.utils import pwd_hg_version, pwd_git_version


class ShubConfig(object):

    def __init__(self):
        self.projects = {}
        self.endpoints = {
            'default': 'https://dash.scrapinghub.com/api/scrapyd/',
        }
        self.apikeys = {}
        self.versions = {}

    def load(self, stream, errmsg=None):
        """
        Load Scrapinghub project/endpoint/auth configuration from stream.
        """
        try:
            yaml_cfg = yaml.safe_load(stream)
            for option in ('projects', 'endpoints', 'apikeys', 'versions'):
                getattr(self, option).update(yaml_cfg.get(option, {}))
        except (yaml.YAMLError, AttributeError):
            # AttributeError: stream is valid YAML but not dictionary-like
            raise ClickException(errmsg or "Unable to parse configuration.")

    def load_file(self, filename):
        """
        Load Scrapinghub project/endpoint/auth configuration from YAML file.
        """
        with open(filename, 'r') as f:
            self.load(
                f,
                "Unable to parse configuration file %s. Maybe a missing "
                "colon?" % filename
            )

    def _parse_project(self, target):
        """Parse project of given target into (project_id, endpoint)."""
        project = self.projects.get(target, target)
        try:
            endpoint, project_id = project.split('/')
        except (ValueError, AttributeError):
            endpoint, project_id = ('default', project)
        try:
            project_id = int(project_id)
        except ValueError:
            raise ClickException(
                "\"%s\" is not a valid Scrapinghub project ID." % project_id
            )
        return project_id, endpoint

    def get_project_id(self, target):
        """Return project ID for given target."""
        return self._parse_project(target)[0]

    def get_endpoint(self, target):
        """Return endpoint for given target."""
        endpoint = self._parse_project(target)[1]
        try:
            return self.endpoints[endpoint]
        except KeyError:
            raise ClickException(
                "Could not find endpoint %s. Please define it in your "
                "scrapinghub.yml." % endpoint
            )

    def get_apikey(self, target, required=True):
        """Return API key for endpoint associated with given target"""
        endpoint = self._parse_project(target)[1]
        try:
            return self.apikeys[endpoint]
        except KeyError:
            if not required:
                return None
            msg = "Could not find API key. Please run 'shub login' first."
            if endpoint != 'default':
                msg = "Could not find API key for endpoint %s." % endpoint
            raise ClickException(msg)

    def get_version(self, target, version=None):
        version = version or self.versions.get(target)
        if version == 'HG':
            return pwd_hg_version()
        elif version == 'GIT':
            return pwd_git_version()
        elif version:
            return str(version)
        return str(int(time.time()))

    def get_target(self, target, auth_required=True):
        """Return (project_id, endpoint, apikey) for given target."""
        return (
            self.get_project_id(target),
            self.get_endpoint(target),
            self.get_apikey(target, required=auth_required),
        )


def _global_scrapinghub_yml(return_nonexistent=False):
    sh_yml = os.path.expanduser("~/.scrapinghub.yml")
    if os.path.exists(sh_yml) or return_nonexistent:
        return sh_yml
    return None


def _closest_scrapinghub_yml(path='.', prevpath=None):
    """
    Return the path to the closest scrapinghub.yml file by traversing the
    current directory and its parents
    """
    if path == prevpath:
        return None
    path = os.path.abspath(path)
    cfgfile = os.path.join(path, 'scrapinghub.yml')
    if os.path.exists(cfgfile):
        return cfgfile
    return _closest_scrapinghub_yml(os.path.dirname(path), path)


def _import_local_scrapycfg(conf):
    from ConfigParser import SafeConfigParser
    from shub import scrapycfg

    closest_scrapycfg = scrapycfg.closest_scrapy_cfg()
    if not closest_scrapycfg:
        return
    cfg = SafeConfigParser()
    cfg.read([closest_scrapycfg])

    targets = scrapycfg.get_targets(cfg)
    if targets == scrapycfg.get_targets(SafeConfigParser()):
        # No deploy configuration in scrapy.cfg
        return
    # TODO: Link to shub documentation will probably change
    click.echo(
        "WARNING: Scrapinghub configuration in scrapy.cfg is deprecated. "
        "Please move your project's scrapinghub configuration to "
        "scrapinghub.yml. See http://doc.scrapinghub.com/shub.html"
    )
    for tname, t in six.iteritems(scrapycfg.get_targets()):
        if 'project' in t:
            conf.projects.update({tname: tname + '/' + t['project']})
        conf.endpoints.update({tname: t['url']})
        if 'username' in t:
            conf.apikeys.update({tname: t['username']})
        if 'version' in t:
            conf.versions.update({tname: t['version']})


def load_shub_config(load_global=True, load_local=True, load_env=True):
    """
    Return a ShubConfig instance with ~/.scrapinghub.yml and the closest
    scrapinghub.yml already loaded
    """
    conf = ShubConfig()
    global_sh_yml = _global_scrapinghub_yml()
    if load_global and global_sh_yml:
        conf.load_file(global_sh_yml)
    if load_env and 'SHUB_APIKEY' in os.environ:
        conf.apikeys['default'] = os.environ['SHUB_APIKEY']
    if load_local:
        closest_sh_yml = _closest_scrapinghub_yml()
        if closest_sh_yml:
            conf.load_file(closest_sh_yml)
        else:
            # For backwards compatibility, try to read deploy targets from
            # project scrapy.cfg (only! not from global ones) if no project
            # scrapinghub.yml found.
            _import_local_scrapycfg(conf)
    return conf


@contextlib.contextmanager
def update_config(conf_path=None):
    """
    Context manager for updating a YAML file while preserving key ordering and
    comments.
    """
    conf_path = conf_path or _global_scrapinghub_yml(return_nonexistent=True)
    try:
        with open(conf_path, 'r') as f:
            conf = yaml.load(f, yaml.RoundTripLoader)
    except IOError as e:
        if e.errno != 2:
            raise
        conf = {}
    # Code inside context manager is executed after this yield
    yield conf
    with open(conf_path, 'w') as f:
        yaml.dump(conf, f, Dumper=yaml.RoundTripDumper)
