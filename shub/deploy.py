from __future__ import absolute_import

import glob
import json
import os
import shutil
import tempfile
from typing import AnyStr, Optional, Union

# Not used in code but needed in runtime, don't remove!
import setuptools
import setuptools.msvc  # noqa

import click
import toml
from six.moves.urllib.parse import urljoin

from shub.config import SH_IMAGES_REGISTRY, list_targets_callback, load_shub_config
from shub.exceptions import BadParameterException, NotFoundException, ShubException
from shub.image.upload import upload_cmd
from shub.utils import (create_default_setup_py, create_scrapinghub_yml_wizard,
                        inside_project, make_deploy_request, run_python)

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
                        targetconf.requirements_file, targetconf.eggs, tmpdir)
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
                stack=None, requirements_file=None, eggs=None, tmpdir=None):
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
            requirements_file = _get_pipfile_requirements(tmpdir)
        elif _is_poetry(requirements_file):
            requirements_file = _get_poetry_requirements()
        elif requirements_file:
            requirements_file = open(requirements_file, 'rb')
        if requirements_file:
            files.append(('requirements', requirements_file))
    except IOError as e:
        raise ShubException("%s %s" % (e.strerror, e.filename))
    files.append(('egg', open(eggpath, 'rb')))
    url = _url(endpoint, 'scrapyd/addversion.json')
    click.echo('Deploying to Scrapy Cloud project "%s"' % project)
    return make_deploy_request(url, data, files, auth, verbose, keep_log)


def _is_pipfile(name):
    return name in ['Pipfile', 'Pipfile.lock']


def _get_pipfile_requirements(tmpdir=None):
    try:
        # moved in pipenv==2022.4.8
        from pipenv.utils.dependencies import convert_deps_to_pip
        from pipenv.utils.indexes import prepare_pip_source_args
    except ImportError:
        try:
            from pipenv.utils import convert_deps_to_pip, prepare_pip_source_args
        except ImportError:
            raise ImportError('You need pipenv installed to deploy with Pipfile')
    try:
        with open('Pipfile.lock') as f:
            pipefile = json.load(f)
            deps = pipefile['default']
            sources_list = prepare_pip_source_args(pipefile['_meta']['sources'])
            sources = ' '.join(sources_list)
    except IOError:
        raise ShubException('Please lock your Pipfile before deploying')
    # We must remove any hash from the pipfile before converting to play nice
    # with vcs packages
    for k, v in deps.items():
        if 'hash' in v:
            del v['hash']
        if 'hashes' in v:
            del v['hashes']
        # Scrapy Cloud also doesn't support editable packages
        if 'editable' in v:
            del v['editable']
    return open(_add_sources(convert_deps_to_pip(deps), _sources=sources.encode(), tmpdir=tmpdir), 'rb')


def _add_sources(
    _requirements: Union[str, list], _sources: bytes, tmpdir: Optional[AnyStr] = None
) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="-requirements.txt", dir=tmpdir)
    tmp.write(_sources + b'\n')
    # Keep backward compatibility with pipenv<=2022.8.30
    if isinstance(_requirements, list):
        tmp.write('\n'.join(_requirements).encode('utf-8'))
    else:
        with open(_requirements, 'rb') as f:
            tmp.write(f.read())
    tmp.flush()
    tmp.close()
    return tmp.name


def _is_poetry(name):
    if name != 'pyproject.toml':
        return False
    data = toml.load(name)
    return 'poetry' in (data.get('tool') or {})


def _get_poetry_requirements():
    try:
        data = toml.load('poetry.lock')
    except IOError:
        raise ShubException('Please make sure the poetry lock file is present')
    # Adapted from poetry 1.0.0a2 poetry/utils/exporter.py
    lines = []
    for package in data['package']:
        source = package.get('source') or {}
        source_type = source.get('type')
        if source_type == 'git':
            line = 'git+{}@{}#egg={}'.format(
                source['url'], source['reference'], package['name']
            )
        elif source_type in ['directory', 'file']:
            line = ''
            line += source['url']
        else:
            line = '{}=={}'.format(package['name'], package['version'])

            if source_type == 'legacy' and source['url']:
                line += ' \\\n'
                line += '    --index-url {}'.format(source['url'])

        line += '\n'
        lines.append(line)
    return ''.join(lines)


def _build_egg():
    if not inside_project():
        raise NotFoundException("No Scrapy project found in this location.")
    create_default_setup_py()
    d = tempfile.mkdtemp(prefix="shub-deploy-")
    run_python(['setup.py', 'clean', '-a', 'bdist_egg', '-d', d])
    egg = glob.glob(os.path.join(d, '*.egg'))[0]
    return egg, d
