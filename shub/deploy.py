import os
import sys
import glob
import shutil
import tempfile
from six.moves.urllib.parse import urljoin
from subprocess import check_call

import click
import setuptools  # not used in code but needed in runtime, don't remove!
_ = setuptools  # NOQA

from shub.utils import closest_file, get_config, inside_project, retry_on_eintr
from shub.click_utils import log
from shub.config import load_shub_config
from shub.utils import make_deploy_request


HELP = """
Deploy the current folder's Scrapy project to Scrapy Cloud.

If you do not supply `target`, the default target from scrapinghub.yml will be
used. Otherwise, you can specify a numerical project ID:

    shub deploy 12345

Or use any of the targets defined in your scrapinghub.yml:

    shub deploy production

To see a list of all defined targets, run:

    shub deploy -l

You can also deploy an existing project egg:

    shub deploy --egg egg_name

Or build an egg without deploying:

    shub deploy --build-egg egg_name
"""

SHORT_HELP = "Deploy Scrapy project to Scrapy Cloud"


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


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
@click.option("-v", "--version", help="the version to use for deploying")
@click.option("-l", "--list-targets", help="list available targets", is_flag=True)
@click.option("-d", "--debug", help="debug mode (do not remove build dir)", is_flag=True)
@click.option("--egg", help="deploy the given egg, instead of building one")
@click.option("--build-egg", help="only build the given egg, don't deploy it")
def cli(target, version, list_targets, debug, egg, build_egg):
    if not inside_project():
        log("Error: no Scrapy project found in this location")
        sys.exit(1)

    conf = load_shub_config()

    if list_targets:
        for name in conf.projects:
            click.echo(name)
        return

    tmpdir = None

    try:
        if build_egg:
            egg, tmpdir = _build_egg()
            log("Writing egg to %s" % build_egg)
            shutil.copyfile(egg, build_egg)
        else:
            project, endpoint, apikey = conf.get_target(target)
            version = version or conf.get_version()
            auth = (apikey, '')

            if egg:
                log("Using egg: %s" % egg)
                egg = egg
            else:
                log("Packing version %s" % version)
                egg, tmpdir = _build_egg()

            _upload_egg(endpoint, egg, project, version, auth)
            click.echo("Run your spiders at: https://dash.scrapinghub.com/p/%s/" % project)
    finally:
        if tmpdir:
            if debug:
                log("Output dir not removed: %s" % tmpdir)
            else:
                shutil.rmtree(tmpdir, ignore_errors=True)


def _url(endpoint, action):
    return urljoin(endpoint, action)


def _upload_egg(endpoint, eggpath, project, version, auth):
    data = {'project': project, 'version': version}
    files = {'egg': ('project.egg', open(eggpath, 'rb'))}
    url = _url(endpoint, 'addversion.json')
    log('Deploying to Scrapy Cloud project "%s"' % project)
    return make_deploy_request(url, data, files, auth)


def _build_egg():
    closest = closest_file('scrapy.cfg')
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
