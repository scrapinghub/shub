from __future__ import absolute_import

import netrc
import os
import warnings
from collections import namedtuple
from urllib.parse import urlparse, urlunparse

import click
import yaml

from shub import DOCS_LINK, CONFIG_DOCS_LINK
from shub.exceptions import (BadParameterException, BadConfigException,
                             ConfigParseException, MissingAuthException,
                             NotFoundException, ShubDeprecationWarning,
                             print_warning)
from shub.utils import (closest_file, get_scrapycfg_targets, get_sources,
                        pwd_hg_version, pwd_git_version, pwd_version,
                        update_yaml_dict)


APIKEY_SHOW_N_CHARS = 6
SH_IMAGES_REGISTRY = 'images.scrapinghub.com'
SH_IMAGES_REPOSITORY = SH_IMAGES_REGISTRY + '/project/{project}'
GLOBAL_SCRAPINGHUB_YML_PATH = os.path.expanduser(
    os.environ.get('SHUB_GLOBAL_CONFIG', '~/.scrapinghub.yml')
)
NETRC_PATH = os.path.expanduser('~/_netrc' if os.name == 'nt' else '~/.netrc')


class ShubConfig(object):

    DEFAULT_ENDPOINT = 'https://app.scrapinghub.com/api/'

    # Dictionary option name: Shortcut to set 'default' key
    SHORTCUTS = {
        'projects': 'project',
        'endpoints': 'endpoint',
        'apikeys': 'apikey',
        'stacks': 'stack',
        'images': 'image',
    }

    def __init__(self):
        self.projects = {}
        self.endpoints = {
            'default': self.DEFAULT_ENDPOINT,
        }
        self.apikeys = {}
        self.version = 'AUTO'
        self.stacks = {}
        self.requirements_file = None
        self.eggs = []
        self.images = {}

    def _check_endpoints(self):
        """Check the endpoints. Send warnings if necessary."""
        for endpoint, url in self.endpoints.items():
            parsed = urlparse(url)
            if parsed.netloc == 'staging.scrapinghub.com':
                self.endpoints[endpoint] = urlunparse(
                    parsed._replace(netloc='app.scrapinghub.com')
                )
                click.echo(
                    'WARNING: Endpoint "%s" is still using %s which has been '
                    'obsoleted. shub has updated it to app.scrapinghub.com '
                    'for this time only. Please update your configuration.' % (
                        endpoint, parsed.netloc,
                    ),
                    err=True
                )
            if parsed.scheme == 'http':
                print_warning(
                    'Endpoint "%s" is still using HTTP. '
                    'Please change it to HTTPS if possible.' % endpoint
                )

    def load(self, stream):
        """Load Scrapinghub configuration from stream."""
        # flag to mark if images/default was used in the config file
        check_default_image_scope = False
        try:
            yaml_cfg = yaml.safe_load(stream)
            if not yaml_cfg:
                return
            for option, shortcut in self.SHORTCUTS.items():
                option_conf = getattr(self, option)
                yaml_option_conf = yaml_cfg.get(option, {})
                option_conf.update(yaml_option_conf)
                if option == 'images' and yaml_option_conf:
                    print_warning(
                        "Images section is deprecated, please replace it with "
                        "global `image` setting or define `image` setting for "
                        "the project.\n  Check for additional details in {}."
                        .format(CONFIG_DOCS_LINK),
                        category=ShubDeprecationWarning
                    )
                    if 'default' in yaml_option_conf:
                        check_default_image_scope = True
                if shortcut in yaml_cfg:
                    # We explicitly check yaml_option_conf and not option_conf.
                    # It is okay to set conflicting defaults if they are in
                    # different files (b/c then one of these will have
                    # priority)
                    if 'default' in yaml_option_conf:
                        raise BadConfigException(
                            "You cannot specify both '%s' and a 'default' key "
                            "for '%s' in the same file" % (shortcut,  option))
                    option_conf['default'] = yaml_cfg[shortcut]
            self.version = yaml_cfg.get('version', self.version)
            self.requirements_file = yaml_cfg.get('requirements_file',
                                                  self.requirements_file)
            self.requirements_file = yaml_cfg.get('requirements', {}).get(
                'file', self.requirements_file)
            self.eggs = yaml_cfg.get('requirements', {}).get('eggs', self.eggs)
        except (yaml.YAMLError, AttributeError):
            # AttributeError: stream is valid YAML but not dictionary-like
            raise ConfigParseException
        # fail if `projects` section has keys not found in `images`
        if (check_default_image_scope and
                not set(self.projects).issubset(set(self.images))):
            raise BadConfigException(
                    "Found ambigious configuration: default image has global "
                    "scope now, but some projects were not using custom "
                    "images and can be broken now. Please fix your config by "
                    "replacing `images` section with `image` settings. Check "
                    "for additional details in {}".format(CONFIG_DOCS_LINK)
                )
        self._check_endpoints()

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

    def _load_scrapycfg_target(self, tname, t):
        default_endpoint = ('url' not in t or
                            t['url'] == self.endpoints['default'])
        default_user = ('username' not in t or
                        t['username'] == self.apikeys.get('default'))
        if 'project' in t:
            if tname == 'default' or (default_endpoint and default_user):
                self.projects[tname] = t['project']
            elif default_endpoint and not default_user:
                self.projects[tname] = {
                    'id': t['project'], 'apikey': tname,
                }
            else:
                self.projects[tname] = tname + '/' + t['project']
        if not default_endpoint:
            self.endpoints[tname] = t['url']
        if not default_user or (not default_endpoint and 'username' in t):
            self.apikeys[tname] = t['username']
        if 'version' in t:
            self.version = t['version']

    def load_scrapycfg(self, sources):
        """Load configuration from a list of scrapy.cfg-like sources."""
        targets = get_scrapycfg_targets(sources)
        self._load_scrapycfg_target('default', targets['default'])
        del targets['default']
        for tname, t in targets.items():
            self._load_scrapycfg_target(tname, t)
        self._check_endpoints()

    def save(self, path=None, options=None):
        def _project_id_as_int(project):
            """Copy project and return it with the ID casted to int to make
            sure it is exported as "123" and not "'123'"
            """
            try:
                if isinstance(project, dict):
                    project = project.copy()
                    project['id'] = int(project['id'])
                else:
                    project = int(project)
            except ValueError:
                # Happens when project ID contains endpoint (e.g. vagrant/123),
                # in that case it will be exported without quotation marks
                # anyway
                pass
            return project

        with update_yaml_dict(path) as yml:
            options = options or list(self.SHORTCUTS)
            for option in options:
                shortcut = self.SHORTCUTS[option]
                conf = getattr(self, option)
                if option == 'endpoints' and conf == ShubConfig().endpoints:
                    # Don't write default endpoint
                    continue
                elif option == 'projects':
                    conf = {k: _project_id_as_int(v) for k, v in conf.items()}
                if list(conf.keys()) == ['default']:
                    yml[shortcut] = conf['default']
                    yml.pop(option, None)
                else:
                    yml[option] = conf
                    yml.pop(shortcut, None)
            if self.version != 'AUTO':
                yml['version'] = self.version
            if self.eggs:
                yml.setdefault('requirements', {})['eggs'] = self.eggs
            if self.requirements_file:
                yml.setdefault('requirements', {})['file'] = (
                    self.requirements_file)

    @property
    def normalized_projects(self):
        """
        Return a copy of ``self.projects`` where all values are dictionaries
        that have at least the keys ``id``, ``endpoint``, and ``apikey``.
        """
        projects = self.projects.copy()
        for target, proj in list(projects.items()):
            if not isinstance(proj, dict):
                proj = {'id': proj}
                projects[target] = proj
            elif 'id' not in proj:
                raise BadConfigException("Please define an ID for project "
                                         "\"%s\"" % target)
            try:
                proj['endpoint'], proj['id'] = proj['id'].split('/')
            except (ValueError, AttributeError):
                proj.setdefault('endpoint', 'default')
            proj.setdefault('apikey', proj['endpoint'])
            try:
                proj['id'] = int(proj['id'])
            except ValueError:
                raise BadConfigException(
                    "\"%s\" is not a valid Scrapinghub project ID. Please "
                    "check your scrapinghub.yml" % proj['id']
                )
        return projects

    def get_project(self, project):
        """
        Given a project alias or a canonical project ID, return the
        corresponding normalized configuration dictionary from
        ``self.projects``.
        """
        if project in self.projects:
            return self.normalized_projects[project]
        try:
            endpoint, proj_id = project.split('/')
        except (ValueError, AttributeError):
            endpoint, proj_id = 'default', project
        try:
            proj_id = int(proj_id)
        except ValueError:
            if project == 'default':
                msg = ("Please specify target or configure a default target "
                       "in scrapinghub.yml.")
            else:
                msg = ("Could not find target \"%s\". Please define it in "
                       "your scrapinghub.yml or supply a numerical project ID."
                       "" % project)
            raise BadParameterException(msg, param_hint='target')
        for proj in self.normalized_projects.values():
            if proj['id'] == proj_id and proj['endpoint'] == endpoint:
                return proj
        else:
            return {'id': proj_id, 'endpoint': endpoint, 'apikey': endpoint}

    def get_version(self):
        if not self.version or self.version == 'AUTO':
            return pwd_version()
        elif self.version == 'GIT':
            return pwd_git_version()
        elif self.version == 'HG':
            return pwd_hg_version()
        elif self.version:
            return str(self.version)

    def get_target_conf(self, target, auth_required=True):
        proj = self.get_project(target)
        if proj['endpoint'] not in self.endpoints:
            raise NotFoundException("Could not find endpoint %s. Please "
                                    "define it in your scrapinghub.yml."
                                    "" % proj['endpoint'])
        try:
            apikey = str(self.apikeys[proj['apikey']])
        except KeyError:
            if auth_required:
                msg = None
                if proj['endpoint'] != 'default':
                    msg = ("Could not find API key for endpoint %s."
                           "" % proj['endpoint'])
                raise MissingAuthException(msg)
            apikey = None
        return Target(
            project_id=proj['id'],
            endpoint=self.endpoints[proj['endpoint']],
            apikey=apikey,
            stack=(self.stacks.get(proj['stack'], proj['stack'])
                   if 'stack' in proj else self.stacks.get('default')),
            image=self._select_image_for_project(target, proj),
            requirements_file=self.requirements_file,
            version=self.get_version(),
            eggs=self.eggs,
        )

    def _select_image_for_project(self, target, project):
        """Helper to select image for a project (or its target).

        The select logic is the following:
        - image defined per project has highest priority,
        - images section is marked as deprecated, but still in force:
          if target is defined in images - use a corresponding image,
        - if image is not defined, but there's a default image set by
          image or images/default settings - use it.

        The function responds with a custom image name string
        (or None/False meaning regular stack-based deploy).
        """
        image = project.get('image', self.images.get(
            target, self.images.get('default')))
        # aliases to use internal scrapinghub registry as image storage
        if image is True or image == 'scrapinghub':
            image = SH_IMAGES_REPOSITORY.format(project=project['id'])
        return image

    def get_target(self, target, auth_required=True):
        """Return (project_id, endpoint, apikey) for given target."""
        warnings.warn("get_target is deprecated, use get_target_conf instead")
        targetconf = self.get_target_conf(target, auth_required=auth_required)
        return (
            targetconf.project_id,
            targetconf.endpoint,
            targetconf.apikey
        )

    def get_project_id(self, target):
        return self.get_target_conf(target, auth_required=False).project_id

    def get_endpoint(self, target):
        return self.get_target_conf(target, auth_required=False).endpoint

    def get_apikey(self, target, required=True):
        apikey = self.get_target_conf(target, auth_required=required).apikey
        return getattr(apikey, 'value', apikey)

    def get_image(self, target):
        """Return image for a given target."""
        target_conf = self.get_target_conf(target, auth_required=False)
        project, image = target_conf.project_id, target_conf.image
        if image is None:
            raise NotFoundException(
                "Could not find image for project '{}'. Please define it "
                "in your scrapinghub.yml.".format(target))
        elif image is False:
            raise BadConfigException(
                "Using custom images is disabled for the project '{}'. "
                "Please enable it in your scrapinghub.yml.".format(target))
        elif target_conf.stack:
            raise BadConfigException(
                "Ambiguous configuration: There is both a custom image and a "
                "stack configured for project '{}'. Please see {} for "
                "information on how to configure both custom image-based and "
                "stack-based projects.".format(target, CONFIG_DOCS_LINK))
        default_image = SH_IMAGES_REPOSITORY.format(project=project)
        if image.startswith(SH_IMAGES_REGISTRY) and image != default_image:
            raise BadConfigException(
                "Found wrong SH repository for project '{}': expected {}.\n  "
                "Please use aliases `True` or `scrapinghub` to fix it in your "
                "config.".format(target, default_image))
        return image


_Target = namedtuple('Target', ['project_id', 'endpoint', 'apikey', 'stack',
                                'image', 'requirements_file', 'version',
                                'eggs'])


class APIkey(str):

    def __new__(cls, *args, **kwargs):
        cls._inst = super(APIkey, cls).__new__(cls, *args, **kwargs)
        return cls._inst

    def __init__(self, value=None):
        self.value = value

    def __repr__(self):
        if not self.value:
            return ''
        visible_chars = APIKEY_SHOW_N_CHARS
        return (self.value[:visible_chars] +
                'X' * max(len(self.value) - visible_chars, 0))


class Target(_Target):

    def __new__(cls, project_id, endpoint, apikey, *args, **kwargs):
        cls._inst = super(Target, cls).__new__(cls, project_id, endpoint,
                                               APIkey(apikey), *args, **kwargs)
        return cls._inst


MIGRATION_BANNER = """
-------------------------------------------------------------------------------
Welcome to shub version 2!

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

Visit {docs_link} for more information on the new configuration format and
its benefits.

Happy scraping!
-------------------------------------------------------------------------------
""".format(docs_link=DOCS_LINK)


def _migrate_to_global_scrapinghub_yml():
    conf = ShubConfig()
    conf.load_scrapycfg(get_sources(use_closest=False))
    try:
        info = netrc.netrc(NETRC_PATH)
        netrc_key, _, _ = info.authenticators("scrapinghub.com")
    except (IOError, TypeError):
        netrc_key = None
    if netrc_key:
        conf.apikeys['default'] = netrc_key
    conf.save(GLOBAL_SCRAPINGHUB_YML_PATH)
    default_conf = ShubConfig()
    migrated_data = any(getattr(conf, attr) != getattr(default_conf, attr)
                        for attr in ('projects', 'endpoints', 'apikeys',
                                     'version'))
    if migrated_data:
        click.echo(MIGRATION_BANNER, err=True)


PROJECT_MIGRATION_OK_BANNER = """
INFO: Your deploy configuration has been migrated to scrapinghub.yml.
shub will no longer read from scrapy.cfg (but Scrapy will, so don't delete it).
Visit {docs_link} for more information.
""".format(docs_link=DOCS_LINK)


PROJECT_MIGRATION_FAILED_BANNER = """
WARNING: shub failed to convert your scrapy.cfg to scrapinghub.yml. Please
visit {docs_link} for help on how to use the new configuration format. We
would be grateful if you could also file a bug report at
https://github.com/scrapinghub/shub/issues

For now, shub fell back to reading from scrapy.cfg, everything should work as
expected.
""".format(docs_link=DOCS_LINK)


def _migrate_and_load_scrapy_cfg(conf):
    # Load from closest scrapy.cfg
    closest_scrapycfg = closest_file('scrapy.cfg')
    if not closest_scrapycfg:
        return
    targets = get_scrapycfg_targets([closest_scrapycfg])
    if targets == get_scrapycfg_targets():
        # No deploy configuration in scrapy.cfg
        return
    conf.load_scrapycfg([closest_scrapycfg])
    # Migrate to scrapinghub.yml
    closest_sh_yml = os.path.join(os.path.dirname(closest_scrapycfg),
                                  'scrapinghub.yml')
    temp_conf = ShubConfig()
    temp_conf.load_scrapycfg([closest_scrapycfg])
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


def get_target(target, auth_required=True):
    """Load shub configuration and return target."""
    conf = load_shub_config()
    return conf.get_target(target, auth_required=auth_required)


def get_target_conf(target, auth_required=True):
    """Load shub configuration and return target."""
    conf = load_shub_config()
    return conf.get_target_conf(target, auth_required=auth_required)


def get_version():
    """Load shub configuratoin and return version."""
    conf = load_shub_config()
    return conf.get_version()


def list_targets_callback(ctx, param, value):
    """Click option callback to get targets from config, print it and exit."""
    if not value:
        return
    conf = load_shub_config()
    for name in conf.projects:
        click.echo(name)
    ctx.exit()
