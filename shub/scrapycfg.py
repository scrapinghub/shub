import time

from shub.click_utils import fail
from shub.utils import pwd_hg_version, pwd_git_version


def get_project(target, project):
    project = project or target.get('project')
    if not project:
        raise fail("Error: Missing project id")
    return str(project)


def get_targets():
    cfg = get_config()
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
