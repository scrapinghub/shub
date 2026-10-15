import os
import warnings
from collections import namedtuple
from urllib.parse import urlparse, urlunparse

import click
import yaml
from dotenv import dotenv_values, find_dotenv

from shub import CONFIG_DOCS_LINK
from shub.exceptions import (BadParameterException, BadConfigException,
                             ConfigParseException, MissingAuthException,
                             NotFoundException, ShubDeprecationWarning,
                             print_warning)
from shub.utils import (closest_file, pwd_hg_version, pwd_git_version,
                        pwd_version, update_yaml_dict)

APIKEY_SHOW_N_CHARS = 6
SH_IMAGES_REGISTRY = 'images.scrapinghub.com'
SH_IMAGES_REPOSITORY = SH_IMAGES_REGISTRY + '/project/{project}'
GLOBAL_SCRAPINGHUB_YML_PATH = os.path.expanduser(
    os.environ.get('SHUB_GLOBAL_CONFIG', '~/.scrapinghub.yml')
)


class ShubConfig:

    DEFAULT_ENDPOINT = 'https://app.zyte.com/api/'

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
                    parsed._replace(netloc='app.zyte.com')
                )
                click.echo(
                    'WARNING: Endpoint "%s" is still using %s which has been '
                    'obsoleted. shub has updated it to app.zyte.com '
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
            with open(filename) as f:
                self.load(f)
        except ConfigParseException:
            raise ConfigParseException(
                "Unable to parse configuration file %s. Maybe a missing "
                "colon?" % filename
            )

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
        proj_requirements = proj.get('requirements', {})
        requirements = proj_requirements.get('file', self.requirements_file)
        eggs = proj_requirements.get('eggs', self.eggs)
        return Target(
            project_id=proj['id'],
            endpoint=self.endpoints[proj['endpoint']],
            apikey=apikey,
            stack=(self.stacks.get(proj['stack'], proj['stack'])
                   if 'stack' in proj else self.stacks.get('default')),
            image=self._select_image_for_project(target, proj),
            requirements_file=requirements,
            version=self.get_version(),
            eggs=eggs,
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
        cls._inst = super().__new__(cls, *args, **kwargs)
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
        cls._inst = super().__new__(cls, project_id, endpoint,
                                    APIkey(apikey), *args, **kwargs)
        return cls._inst


def _load_dotenv_apikey(dotenv_path: str | None = None) -> None:
    """Load SHUB_APIKEY from a .env file into the environment.

    Only the SHUB_APIKEY variable is read from the file; any other variables are ignored.
    A SHUB_APIKEY already present in the environment takes precedence over the value in
    the file. When ``dotenv_path`` is None, the nearest ``.env`` file in the current
    directory or its parents is used.
    """
    if 'SHUB_APIKEY' in os.environ:
        return
    apikey = dotenv_values(dotenv_path or find_dotenv(usecwd=True)).get('SHUB_APIKEY')
    if apikey:
        os.environ['SHUB_APIKEY'] = apikey


def load_shub_config(load_global=True, load_local=True, load_env=True):
    """
    Return a ShubConfig instance with ~/.scrapinghub.yml and the closest
    scrapinghub.yml already loaded
    """
    conf = ShubConfig()
    if load_global and os.path.exists(GLOBAL_SCRAPINGHUB_YML_PATH):
        conf.load_file(GLOBAL_SCRAPINGHUB_YML_PATH)
    if load_local:
        closest_sh_yml = closest_file('scrapinghub.yml')
        if closest_sh_yml:
            conf.load_file(closest_sh_yml)
    if load_env:
        _load_dotenv_apikey()
        if 'SHUB_APIKEY' in os.environ:
            conf.apikeys['default'] = os.environ['SHUB_APIKEY']
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
