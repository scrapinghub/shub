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
from scrapinghub import Connection, APIError

from shub.config import load_shub_config, update_yaml_dict
from shub.exceptions import (InvalidAuthException, NotFoundException,
                             RemoteErrorException)
from shub.utils import (closest_file, get_config, inside_project,
                        make_deploy_request, patch_sys_executable,
                        retry_on_eintr)


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


def list_targets(ctx, param, value):
    if not value:
        return
    conf = load_shub_config()
    for name in conf.projects:
        click.echo(name)
    ctx.exit()


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
@click.option("-l", "--list-targets", help="list available targets",
              is_flag=True, is_eager=True, expose_value=False,
              callback=list_targets)
@click.option("-V", "--version", help="the version to use for deploying")
@click.option("-d", "--debug", help="debug mode (do not remove build dir)",
              is_flag=True)
@click.option("--egg", help="deploy the given egg, instead of building one")
@click.option("--build-egg", help="only build the given egg, don't deploy it")
@click.option("-v", "--verbose", help="stream deploy logs to console",
              is_flag=True)
@click.option("-k", "--keep-log", help="keep the deploy log", is_flag=True)
def cli(target, version, debug, egg, build_egg, verbose, keep_log):
    if not inside_project():
        raise NotFoundException("No Scrapy project found in this location.")
    tmpdir = None
    try:
        if build_egg:
            egg, tmpdir = _build_egg()
            click.echo("Writing egg to %s" % build_egg)
            shutil.copyfile(egg, build_egg)
        else:
            conf = load_shub_config()
            if target == 'default' and target not in conf.projects:
                _deploy_wizard(conf)
            targetconf = conf.get_targetconf(target)
            project = targetconf.project_id
            endpoint = targetconf.endpoint
            apikey = targetconf.apikey
            stack = targetconf.stack
            requirements_file = targetconf.requirements_file
            version = version or conf.get_version()
            auth = (apikey, '')

            if egg:
                click.echo("Using egg: %s" % egg)
                egg = egg
            else:
                click.echo("Packing version %s" % version)
                egg, tmpdir = _build_egg()

            _upload_egg(endpoint, egg, project, version, auth,
                        verbose, keep_log, stack, requirements_file)
            click.echo("Run your spiders at: "
                       "https://dash.scrapinghub.com/p/%s/" % project)
    finally:
        if tmpdir:
            if debug:
                click.echo("Output dir not removed: %s" % tmpdir)
            else:
                shutil.rmtree(tmpdir, ignore_errors=True)


def _url(endpoint, action):
    return urljoin(endpoint, action)


def _upload_egg(endpoint, eggpath, project, version, auth, verbose, keep_log,
                stack=None, requirements_file=None):
    data = {'project': project, 'version': version}
    if stack:
        data['stack'] = stack
    files = {'egg': ('project.egg', open(eggpath, 'rb'))}
    if requirements_file:
        files['requirements'] = ('requirements.txt',
                                 open(requirements_file, 'rb'))
    url = _url(endpoint, 'scrapyd/addversion.json')
    click.echo('Deploying to Scrapy Cloud project "%s"' % project)
    return make_deploy_request(url, data, files, auth, verbose, keep_log)


def _build_egg():
    closest = closest_file('scrapy.cfg')
    os.chdir(os.path.dirname(closest))
    if not os.path.exists('setup.py'):
        settings = get_config().get('settings', 'default')
        _create_default_setup_py(settings=settings)
    d = tempfile.mkdtemp(prefix="shub-deploy-")
    with open(os.path.join(d, "stdout"), "wb") as o, \
            open(os.path.join(d, "stderr"), "wb") as e, \
            patch_sys_executable():
        retry_on_eintr(
            check_call,
            [sys.executable, 'setup.py', 'clean', '-a', 'bdist_egg', '-d', d],
            stdout=o, stderr=e,
        )
    egg = glob.glob(os.path.join(d, '*.egg'))[0]
    return egg, d


def _create_default_setup_py(**kwargs):
    with open('setup.py', 'w') as f:
        f.write(_SETUP_PY_TEMPLATE % kwargs)


def _has_project_access(project, endpoint, apikey):
    conn = Connection(apikey, url=endpoint)
    try:
        return project in conn.project_ids()
    except APIError as e:
        if 'Authentication failed' in e.message:
            raise InvalidAuthException
        else:
            raise RemoteErrorException(e.message)


def _deploy_wizard(conf, target='default'):
    """
    Ask user for project ID, ensure they have access to that project, and save
    it to given ``target`` in local ``scrapinghub.yml`` if desired.
    """
    closest_scrapycfg = closest_file('scrapy.cfg')
    # Double-checking to make deploy_wizard() independent of cli()
    if not closest_scrapycfg:
        raise NotFoundException("No Scrapy project found in this location.")
    closest_sh_yml = os.path.join(os.path.dirname(closest_scrapycfg),
                                  'scrapinghub.yml')
    # Get default endpoint and API key (meanwhile making sure the user is
    # logged in)
    endpoint, apikey = conf.get_endpoint(0), conf.get_apikey(0)
    project = click.prompt("Target project ID", type=int)
    if not _has_project_access(project, endpoint, apikey):
        raise InvalidAuthException(
            "The account you logged in to has no access to project {}. Please "
            "double-check the project ID and make sure you logged in to the "
            "correct acount.".format(project),
        )
    conf.projects[target] = project
    if click.confirm("Save as default", default=True):
        try:
            with update_yaml_dict(closest_sh_yml) as conf_yml:
                default_entry = {'default': project}
                if 'projects' in conf_yml:
                    conf_yml['projects'].update(default_entry)
                else:
                    conf_yml['projects'] = default_entry
        except Exception:
            click.echo(
                "There was an error while trying to write to scrapinghub.yml. "
                "Could not save project {} as default.".format(project),
            )
        else:
            click.echo(
                "Project {} was set as default in scrapinghub.yml. You can "
                "deploy to it via 'shub deploy' from now on.".format(project),
            )
