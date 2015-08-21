import os
import sys
import glob
import shutil
import tempfile
from six.moves.urllib.parse import urljoin
from subprocess import check_call

import click
import setuptools  # not used in code but needed in runtime, don't remove!
_ = setuptools

from scrapy.utils.project import inside_project
from scrapy.utils.python import retry_on_eintr
from scrapy.utils.conf import get_config, closest_scrapy_cfg

from shub.click_utils import log
from shub.utils import make_deploy_request
from shub.auth import find_api_key
from shub import scrapycfg


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
        for name, target in scrapycfg.get_targets().items():
            click.echo(name)
        return

    tmpdir = None

    try:
        if build_egg:
            egg, tmpdir = _build_egg()
            log("Writing egg to %s" % build_egg)
            shutil.copyfile(egg, build_egg)
        else:
            target = scrapycfg.get_target(target)
            project = scrapycfg.get_project(target, project)
            version = scrapycfg.get_version(target, version)
            auth = (find_api_key(), '')

            if egg:
                log("Using egg: %s" % egg)
                egg = egg
            else:
                log("Packing version %s" % version)
                egg, tmpdir = _build_egg()

            _upload_egg(target, egg, project, version, auth)
            click.echo("Run your spiders at: https://dash.scrapinghub.com/p/%s/" % project)
    finally:
        if tmpdir:
            if debug:
                log("Output dir not removed: %s" % tmpdir)
            else:
                shutil.rmtree(tmpdir, ignore_errors=True)


def _url(target, action):
    return urljoin(target['url'], action)


def _upload_egg(target, eggpath, project, version, auth):
    data = {'project': project, 'version': version}
    files = {'egg': ('project.egg', open(eggpath, 'rb'))}
    url = _url(target, 'addversion.json')
    log('Deploying to Scrapy Cloud project "%s"' % project)
    return make_deploy_request(url, data, files, auth)


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
