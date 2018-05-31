from __future__ import absolute_import
import os
import glob
import shutil
import tempfile
import json
from six.moves.urllib.parse import urljoin

import click
# Not used in code but needed in runtime, don't remove!
import setuptools
_1 = setuptools  # NOQA
try:
    # Only available in setuptools >= 24.0.0
    import setuptools.msvc
except ImportError:
    pass
else:
    _2 = setuptools.msvc  # NOQA

from shub.config import (list_targets_callback, load_shub_config,
                         SH_IMAGES_REGISTRY)
from shub.exceptions import (BadParameterException, NotFoundException,
                             ShubException)
from shub.utils import (create_default_setup_py, create_scrapinghub_yml_wizard,
                        inside_project, make_deploy_request, run_python)
from shub.image.upload import upload_cmd


HELP = """
Deploy the current folder's Scrapy project to Scrapy Cloud.

If you do not supply `target`, the default target from scrapinghub.yml will be
used. If you have no scrapinghub.yml, you will be guided through a short wizard
to create one. You can also specify a numerical project ID:

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


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
@click.option("-l", "--list-targets", is_flag=True, is_eager=True,
              expose_value=False, callback=list_targets_callback,
              help="List available project names defined in your config")
@click.option("-V", "--version", help="The version to use for deploying")
@click.option("-d", "--debug", help="Debug mode (do not remove build dir)",
              is_flag=True)
@click.option("--egg", help="Deploy the given egg, instead of building one")
@click.option("--build-egg", help="Only build the given egg, don't deploy it")
@click.option("-v", "--verbose", help="Stream deploy logs to console",
              is_flag=True)
@click.option("-k", "--keep-log", help="Keep the deploy log", is_flag=True)
@click.option("--ignore-size", help="Ignore deploy request's egg(s) size check",
              is_flag=True)
def cli(target, version, debug, egg, build_egg, verbose, keep_log,
        ignore_size):
    conf, image = load_shub_config(), None
    if not build_egg:
        create_scrapinghub_yml_wizard(conf, target=target)
    image = conf.get_target_conf(target).image
    if not image:
        deploy_cmd(target, version, debug, egg, build_egg, verbose, keep_log,
                   conf=conf)
    elif image.startswith(SH_IMAGES_REGISTRY):
        upload_cmd(target, version)
    else:
        raise BadParameterException(
            "Please use `shub image` commands to work with Docker registries "
            "other than Scrapinghub default registry.")


def deploy_cmd(target, version, debug, egg, build_egg, verbose, keep_log,
               conf=None):
    tmpdir = None
    try:
        if build_egg:
            egg, tmpdir = _build_egg()
            click.echo("Writing egg to %s" % build_egg)
            shutil.copyfile(egg, build_egg)
        else:
            conf = conf or load_shub_config()
            targetconf = conf.get_target_conf(target)
            version = version or targetconf.version
            auth = (targetconf.apikey, '')

            if egg:
                click.echo("Using egg: %s" % egg)
                egg = egg
            else:
                click.echo("Packing version %s" % version)
                egg, tmpdir = _build_egg()

            _upload_egg(targetconf.endpoint, egg, targetconf.project_id,
                        version, auth, verbose, keep_log, targetconf.stack,
                        targetconf.requirements_file, targetconf.eggs)
            click.echo("Run your spiders at: "
                       "https://app.scrapinghub.com/p/%s/"
                       "" % targetconf.project_id)
    finally:
        if tmpdir:
            if debug:
                click.echo("Output dir not removed: %s" % tmpdir)
            else:
                shutil.rmtree(tmpdir, ignore_errors=True)


def _url(endpoint, action):
    return urljoin(endpoint, action)


def _upload_egg(endpoint, eggpath, project, version, auth, verbose, keep_log,
                stack=None, requirements_file=None, eggs=None):
    expanded_eggs = []
    for e in (eggs or []):
        # Expand glob patterns, but make sure we don't swallow non-existing
        # eggs that were directly named
        # (glob.glob('non_existing_file') returns [])
        if any(['*' in e, '?' in e, '[' in e and ']' in e]):
            # Never match the main egg
            expanded_eggs.extend(
                [x for x in glob.glob(e)
                 if os.path.abspath(x) != os.path.abspath(eggpath)])
        else:
            expanded_eggs.append(e)

    data = {'project': project, 'version': version}
    if stack:
        data['stack'] = stack

    try:
        files = [('eggs', open(path, 'rb')) for path in expanded_eggs]
        if _is_pipfile(requirements_file):
            requirements_file = _get_pipfile_requirements()
        if requirements_file:
            files.append(('requirements', open(requirements_file, 'rb')))
    except IOError as e:
        raise ShubException("%s %s" % (e.strerror, e.filename))
    files.append(('egg', open(eggpath, 'rb')))
    url = _url(endpoint, 'scrapyd/addversion.json')
    click.echo('Deploying to Scrapy Cloud project "%s"' % project)
    return make_deploy_request(url, data, files, auth, verbose, keep_log)


def _is_pipfile(name):
    return name in ['Pipfile', 'Pipfile.lock']


def _get_pipfile_requirements():
    try:
        from pipenv.utils import convert_deps_to_pip
    except ImportError:
        raise ImportError('You need pipenv installed to deploy with Pipfile')
    try:
        with open('Pipfile.lock') as f:
            deps = json.load(f)['default']
    except IOError:
        raise ShubException('Please lock your Pipfile before deploying')
    return convert_deps_to_pip(deps)


def _build_egg():
    if not inside_project():
        raise NotFoundException("No Scrapy project found in this location.")
    create_default_setup_py()
    d = tempfile.mkdtemp(prefix="shub-deploy-")
    run_python(['setup.py', 'clean', '-a', 'bdist_egg', '-d', d])
    egg = glob.glob(os.path.join(d, '*.egg'))[0]
    return egg, d
