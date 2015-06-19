import os
import sys
import glob
import time
import netrc
import shutil
import tempfile
from urlparse import urlparse, urljoin
from subprocess import check_call

import click
import setuptools  # not used in code but needed in runtime, don't remove!
_ = setuptools

from scrapy.utils.project import inside_project
from scrapy.utils.python import retry_on_eintr
from scrapy.utils.conf import get_config, closest_scrapy_cfg

from shub.click_utils import log, fail
from shub.utils import make_deploy_request, pwd_hg_version, pwd_git_version


_SETUP_PY_TEMPLATE = """\
# Automatically created by: shub deploy

from setuptools import setup, find_packages

setup(
    name         = 'project',
    version      = '1.0',
    packages     = find_packages(),
    entry_points = {'scrapy': ['settings = %(settings)s']},
)
"""


@click.command(help="Deploy Scrapy project to Scrapy Cloud")
@click.argument("target", required=False, default="default")
@click.option("-p", "--project", help="the project ID to deploy to", type=click.INT)
@click.option("-v", "--version", help="the version to use for deploying")
@click.option("-l", "--list-targets", help="list available targets", is_flag=True)
@click.option("-d", "--debug", help="debug mode (do not remove build dir)", is_flag=True)
@click.option("--egg", help="deploy the given egg, instead of building one")
@click.option("--build-egg", help="only build the given egg, don't deploy it")
def cli(target, project, version, list_targets, debug, egg, build_egg):
    if not inside_project():
        log("Error: no Scrapy project found in this location")
        sys.exit(1)

    if list_targets:
        for name, target in _get_targets().items():
            click.echo(name)
        return

    tmpdir = None

    if build_egg:
        egg, tmpdir = _build_egg()
        log("Writing egg to %s" % build_egg)
        shutil.copyfile(egg, build_egg)
    else:
        target = _get_target(target)
        project = _get_project(target, project)
        version = _get_version(target, version)
        if egg:
            log("Using egg: %s" % egg)
            egg = egg
        else:
            log("Packing version %s" % version)
            egg, tmpdir = _build_egg()

        _upload_egg(target, egg, project, version)
        click.echo("Run your spiders at: https://dash.scrapinghub.com/p/%s/" % project)

    if tmpdir:
        if debug:
            log("Output dir not removed: %s" % tmpdir)
        else:
            shutil.rmtree(tmpdir)


def _get_project(target, project):
    project = project or target.get('project')
    if not project:
        raise fail("Error: Missing project id")
    return str(project)


def _get_option(section, option, default=None):
    cfg = get_config()
    return cfg.get(section, option) if cfg.has_option(section, option) \
        else default


def _get_targets():
    cfg = get_config()
    baset = dict(cfg.items('deploy')) if cfg.has_section('deploy') else {}
    baset.setdefault('url', 'http://dash.scrapinghub.com/api/scrapyd/')
    targets = {}
    targets['default'] = baset
    for x in cfg.sections():
        if x.startswith('deploy:'):
            t = baset.copy()
            t.update(cfg.items(x))
            targets[x[7:]] = t
    return targets


def _get_target(name):
    try:
        return _get_targets()[name]
    except KeyError:
        raise fail("Unknown target: %s" % name)


def _url(target, action):
    return urljoin(target['url'], action)


def _get_version(target, version):
    version = version or target.get('version')
    if version == 'HG':
        return pwd_hg_version()
    elif version == 'GIT':
        return pwd_git_version()
    elif version:
        return str(version)
    else:
        return str(int(time.time()))


def _upload_egg(target, eggpath, project, version):
    data = {'project': project, 'version': version}
    files = {'egg': ('project.egg', open(eggpath, 'rb'))}
    url = _url(target, 'addversion.json')
    auth = _get_auth(target)

    log('Deploying to Scrapy Cloud project "%s"' % project)
    return make_deploy_request(url, data, files, auth)


def _get_auth(target):
    if 'username' in target:
        return (target.get('username'), target.get('password', ''))
    # try netrc
    try:
        host = urlparse(target['url']).hostname
        a = netrc.netrc().authenticators(host)
        return (a[0], a[2])
    except (netrc.NetrcParseError, IOError, TypeError):
        pass


def _build_egg():
    closest = closest_scrapy_cfg()
    os.chdir(os.path.dirname(closest))
    if not os.path.exists('setup.py'):
        settings = get_config().get('settings', 'default')
        _create_default_setup_py(settings=settings)
    d = tempfile.mkdtemp(prefix="shub-deploy-")
    o = open(os.path.join(d, "stdout"), "wb")
    e = open(os.path.join(d, "stderr"), "wb")
    retry_on_eintr(check_call,
                   [sys.executable, 'setup.py', 'clean', '-a', 'bdist_egg', '-d', d],
                   stdout=o, stderr=e)
    o.close()
    e.close()
    egg = glob.glob(os.path.join(d, '*.egg'))[0]
    return egg, d


def _create_default_setup_py(**kwargs):
    with open('setup.py', 'w') as f:
        f.write(_SETUP_PY_TEMPLATE % kwargs)
