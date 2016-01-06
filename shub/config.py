import contextlib
import netrc
import os
import time

import click
import six
import ruamel.yaml as yaml

from shub.exceptions import (BadParameterException, BadConfigException,
                             ConfigParseException, MissingAuthException,
                             NotFoundException)
from shub.utils import (closest_file, get_scrapycfg_targets, get_sources,
                        pwd_hg_version, pwd_git_version)


GLOBAL_SCRAPINGHUB_YML_PATH = os.path.expanduser("~/.scrapinghub.yml")
NETRC_PATH = os.path.expanduser('~/_netrc' if os.name == 'nt' else '~/.netrc')


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
            if not yaml_cfg:
                return
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

    def _load_scrapycfg(self, sources):
        """Load configuration from a list of scrapy.cfg-like sources."""
        targets = get_scrapycfg_targets(sources)
        for tname, t in six.iteritems(targets):
            if 'project' in t:
                prefix = '' if tname == 'default' else tname + '/'
                self.projects.update({tname: prefix + t['project']})
            if 'url' in t:
                self.endpoints.update({tname: t['url']})
            if 'username' in t:
                self.apikeys.update({tname: t['username']})
            if 'version' in t:
                self.version = t['version']

    def save(self, path=None):
        with update_config(path) as yml:
            yml['projects'] = self.projects
            yml['endpoints'] = self.endpoints
            yml['apikeys'] = self.apikeys
            yml['version'] = self.version
            # Don't write defaults
            if self.endpoints['default'] == ShubConfig.DEFAULT_ENDPOINT:
                del yml['endpoints']['default']
            if self.version == 'AUTO':
                del yml['version']

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
            if target == 'default':
                raise BadParameterException(
                    "Please specify target or configure a default target in "
                    "scrapinghub.yml.",
                    param_hint='target',
                )
            elif target in self.projects:
                raise BadConfigException(
                    "\"%s\" is not a valid Scrapinghub project ID. Please "
                    "check your scrapinghub.yml" % project_id,
                )
            raise BadParameterException(
                "Could not find target \"%s\". Please define it in your "
                "scrapinghub.yml or supply a numerical project ID."
                "" % project_id,
                param_hint='target',
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


MIGRATION_BANNER = """
-------------------------------------------------------------------------------
Welcome to shub v1.6!

This release contains major updates to how shub is configured, as well as
updates to the commands and shub's look & feel.

Run 'shub' to get an overview over all available commands, and
'shub command --help' to get detailed help on a command. Definitely try the
new 'shub items -f [JOBID]' to see items live as they are being scraped!

From now on, shub configuration should be done in a file called
'scrapinghub.yml', living next to the previously used 'scrapy.cfg' in your
Scrapy project directory. Global configuration, for example API keys, should be
done in a file called '.scrapinghub.yml' in your home directory.

But no worries, shub has automatically migrated your global settings to
~/.scrapinghub.yml, and will also automatically migrate your project settings
when you run a command within a Scrapy project.

Visit http://doc.scrapinghub.com/shub.html for more information on the new
configuration format and its benefits.

Happy scraping!
-------------------------------------------------------------------------------
"""


def _migrate_to_global_scrapinghub_yml():
    conf = ShubConfig()
    conf._load_scrapycfg(get_sources(use_closest=False))
    try:
        info = netrc.netrc(NETRC_PATH)
        netrc_key, _, _ = info.authenticators("scrapinghub.com")
    except (IOError, TypeError):
        netrc_key = None
    if netrc_key:
        conf.apikeys['default'] = netrc_key
    conf.save()
    default_conf = ShubConfig()
    migrated_data = any(getattr(conf, attr) != getattr(default_conf, attr)
                        for attr in ('projects', 'endpoints', 'apikeys',
                                     'version'))
    if migrated_data:
        click.echo(MIGRATION_BANNER, err=True)


PROJECT_MIGRATION_OK_BANNER = """
INFO: Your project configuration has been migrated to scrapinghub.yml.
shub will no longer read from scrapy.cfg. Visit
http://doc.scrapinghub.com/shub.html for more information.
"""


PROJECT_MIGRATION_FAILED_BANNER = """
WARNING: shub failed to convert your scrapy.cfg to scrapinghub.yml. Please
visit http://doc.scrapinghub.com/shub.html for help on how to use the new
configuration format. We would be grateful if you could also file a bug report
at https://github.com/scrapinghub/shub/issues

For now, shub fell back to reading from scrapy.cfg, everything should work as
expected.
"""


def _migrate_and_load_scrapy_cfg(conf):
    # Load from closest scrapy.cfg
    closest_scrapycfg = closest_file('scrapy.cfg')
    if not closest_scrapycfg:
        return
    targets = get_scrapycfg_targets([closest_scrapycfg])
    if targets == get_scrapycfg_targets():
        # No deploy configuration in scrapy.cfg
        return
    conf._load_scrapycfg([closest_scrapycfg])
    # Migrate to scrapinghub.yml
    closest_sh_yml = os.path.join(os.path.dirname(closest_scrapycfg),
                                  'scrapinghub.yml')
    temp_conf = ShubConfig()
    temp_conf._load_scrapycfg([closest_scrapycfg])
    try:
        temp_conf.save(closest_sh_yml)
    except Exception:
        click.echo(PROJECT_MIGRATION_FAILED_BANNER, err=True)
    else:
        click.echo(PROJECT_MIGRATION_OK_BANNER, err=True)


def load_shub_config(load_global=True, load_local=True, load_env=True):
    """
    Return a ShubConfig instance with ~/.scrapinghub.yml and the closest
    scrapinghub.yml already loaded
    """
    conf = ShubConfig()
    if load_global:
        if not os.path.exists(GLOBAL_SCRAPINGHUB_YML_PATH):
            _migrate_to_global_scrapinghub_yml()
        conf.load_file(GLOBAL_SCRAPINGHUB_YML_PATH)
    if load_env and 'SHUB_APIKEY' in os.environ:
        conf.apikeys['default'] = os.environ['SHUB_APIKEY']
    if load_local:
        closest_sh_yml = closest_file('scrapinghub.yml')
        if closest_sh_yml:
            conf.load_file(closest_sh_yml)
        else:
            _migrate_and_load_scrapy_cfg(conf)
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
            conf = yaml.load(f, yaml.RoundTripLoader) or {}
    except IOError as e:
        if e.errno != 2:
            raise
        conf = {}
    # Code inside context manager is executed after this yield
    yield conf
    # Avoid writing "key: {}"
    for key in conf.keys():
        if conf[key] == {}:
            del conf[key]
    with open(conf_path, 'w') as f:
        # Avoid writing "{}"
        if conf:
            yaml.dump(conf, f, default_flow_style=False,
                      Dumper=yaml.RoundTripDumper)


def get_target(target, auth_required=True):
    """Load shub configuration and return target."""
    conf = load_shub_config()
    return conf.get_target(target, auth_required=auth_required)


def get_version():
    """Load shub configuratoin and return version."""
    conf = load_shub_config()
    return conf.get_version()
