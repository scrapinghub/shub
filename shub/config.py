from ConfigParser import SafeConfigParser
import contextlib
import os.path
import time

import click
import six
import ruamel.yaml as yaml

from shub.exceptions import (BadParameterException, ConfigParseException,
                             MissingAuthException, NotFoundException)
from shub.utils import closest_file, pwd_hg_version, pwd_git_version


GLOBAL_SCRAPINGHUB_YML_PATH = os.path.expanduser("~/.scrapinghub.yml")


class ShubConfig(object):

    DEFAULT_ENDPOINT = 'https://dash.scrapinghub.com/api/scrapyd/'

    def __init__(self):
        self.projects = {}
        self.endpoints = {
            'default': self.DEFAULT_ENDPOINT,
        }
        self.apikeys = {}
        self.version = 'AUTO'

    def load(self, stream):
        """Load Scrapinghub configuration from stream."""
        try:
            yaml_cfg = yaml.safe_load(stream)
            for option in ('projects', 'endpoints', 'apikeys'):
                getattr(self, option).update(yaml_cfg.get(option, {}))
            self.version = yaml_cfg.get('version', self.version)
        except (yaml.YAMLError, AttributeError):
            # AttributeError: stream is valid YAML but not dictionary-like
            raise ConfigParseException

    def load_file(self, filename):
        """Load Scrapinghub configuration from YAML file. """
        try:
            with open(filename, 'r') as f:
                self.load(f)
        except ConfigParseException:
            raise ConfigParseException(
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
            msg = "\"%s\" is not a valid Scrapinghub project ID." % project_id
            if target == 'default':
                msg = ("Please specify target or configure a default target "
                       "in 'scrapinghub.yml'.")
            raise BadParameterException(msg, param_hint='target')
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
            raise NotFoundException("Could not find endpoint %s. Please define"
                                    " it in your scrapinghub.yml." % endpoint)

    def get_apikey(self, target, required=True):
        """Return API key for endpoint associated with given target"""
        endpoint = self._parse_project(target)[1]
        try:
            return str(self.apikeys[endpoint])
        except KeyError:
            if not required:
                return None
            msg = None
            if endpoint != 'default':
                msg = "Could not find API key for endpoint %s." % endpoint
            raise MissingAuthException(msg)

    def get_version(self):
        if self.version == 'AUTO':
            ver = pwd_git_version()
            if not ver:
                ver = pwd_hg_version()
            if not ver:
                ver = str(int(time.time()))
            return ver
        elif self.version == 'GIT':
            return pwd_git_version()
        elif self.version == 'HG':
            return pwd_hg_version()
        elif self.version:
            return str(self.version)
        return str(int(time.time()))

    def get_target(self, target, auth_required=True):
        """Return (project_id, endpoint, apikey) for given target."""
        return (
            self.get_project_id(target),
            self.get_endpoint(target),
            self.get_apikey(target, required=auth_required),
        )


def _get_scrapycfg_targets(cfgfiles=None):
    cfg = SafeConfigParser()
    cfg.read(cfgfiles or [])
    baset = dict(cfg.items('deploy')) if cfg.has_section('deploy') else {}
    targets = {}
    targets['default'] = baset
    for x in cfg.sections():
        if x.startswith('deploy:'):
            t = baset.copy()
            t.update(cfg.items(x))
            targets[x[7:]] = t
    return targets


def _import_local_scrapycfg(conf):
    closest_scrapycfg = closest_file('scrapy.cfg')
    if not closest_scrapycfg:
        return
    targets = _get_scrapycfg_targets([closest_scrapycfg])
    if targets == _get_scrapycfg_targets():
        # No deploy configuration in scrapy.cfg
        return
    click.echo(
        "WARNING: Configuring Scrapinghub in scrapy.cfg is deprecated. "
        "Please move your project's scrapinghub configuration to "
        "scrapinghub.yml. See http://doc.scrapinghub.com/shub.html"
    )
    for tname, t in six.iteritems(targets):
        if 'project' in t:
            conf.projects.update({tname: tname + '/' + t['project']})
        if 'url' in t:
            conf.endpoints.update({tname: t['url']})
        if 'username' in t:
            conf.apikeys.update({tname: t['username']})
        if 'version' in t:
            conf.version = t['version']


def load_shub_config(load_global=True, load_local=True, load_env=True):
    """
    Return a ShubConfig instance with ~/.scrapinghub.yml and the closest
    scrapinghub.yml already loaded
    """
    conf = ShubConfig()
    if load_global and os.path.exists(GLOBAL_SCRAPINGHUB_YML_PATH):
        conf.load_file(GLOBAL_SCRAPINGHUB_YML_PATH)
    if load_env and 'SHUB_APIKEY' in os.environ:
        conf.apikeys['default'] = os.environ['SHUB_APIKEY']
    if load_local:
        closest_sh_yml = closest_file('scrapinghub.yml')
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
    conf_path = conf_path or GLOBAL_SCRAPINGHUB_YML_PATH
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


def get_target(target, auth_required=True):
    """Load shub configuration and return target."""
    conf = load_shub_config()
    return conf.get_target(target, auth_required=auth_required)


def get_version():
    """Load shub configuratoin and return version."""
    conf = load_shub_config()
    return conf.get_version()
