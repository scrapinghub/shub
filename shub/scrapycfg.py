import os
import time
import warnings

from ConfigParser import SafeConfigParser
from importlib import import_module

from shub.click_utils import fail
from shub.utils import pwd_hg_version, pwd_git_version


def get_project(target, project):
    project = project or target.get('project')
    if not project:
        raise fail("Error: Missing project id")
    return str(project)


def get_targets(cfg=None):
    cfg = cfg or get_config()
    baset = dict(cfg.items('deploy')) if cfg.has_section('deploy') else {}
    baset.setdefault('url', 'https://dash.scrapinghub.com/api/scrapyd/')
    targets = {}
    targets['default'] = baset
    for x in cfg.sections():
        if x.startswith('deploy:'):
            t = baset.copy()
            t.update(cfg.items(x))
            targets[x[7:]] = t
    return targets


def get_target(name):
    try:
        return get_targets()[name]
    except KeyError:
        raise fail("Unknown target: %s" % name)


def get_version(target, version):
    version = version or target.get('version')
    if version == 'HG':
        return pwd_hg_version()
    elif version == 'GIT':
        return pwd_git_version()
    elif version:
        return str(version)
    else:
        return str(int(time.time()))


def get_config(use_closest=True):
    """Get Scrapy config file as a SafeConfigParser"""
    sources = get_sources(use_closest)
    cfg = SafeConfigParser()
    cfg.read(sources)
    return cfg


def get_sources(use_closest=True):
    xdg_config_home = os.environ.get('XDG_CONFIG_HOME') or \
        os.path.expanduser('~/.config')
    sources = ['/etc/scrapy.cfg', r'c:\scrapy\scrapy.cfg',
               xdg_config_home + '/scrapy.cfg',
               os.path.expanduser('~/.scrapy.cfg')]
    if use_closest:
        sources.append(closest_scrapy_cfg())
    return sources


def closest_scrapy_cfg(path='.', prevpath=None):
    """Return the path to the closest scrapy.cfg file by traversing the current
    directory and its parents
    """
    if path == prevpath:
        return ''
    path = os.path.abspath(path)
    cfgfile = os.path.join(path, 'scrapy.cfg')
    if os.path.exists(cfgfile):
        return cfgfile
    return closest_scrapy_cfg(os.path.dirname(path), path)


def inside_project():
    scrapy_module = os.environ.get('SCRAPY_SETTINGS_MODULE')
    if scrapy_module is not None:
        try:
            import_module(scrapy_module)
        except ImportError as exc:
            warnings.warn("Cannot import scrapy settings module %s: %s" % (scrapy_module, exc))
        else:
            return True
    return bool(closest_scrapy_cfg())
