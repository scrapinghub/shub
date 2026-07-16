import glob
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from typing import AnyStr, Optional, Union

# Not used in code but needed in runtime, don't remove!
import setuptools
import setuptools.msvc  # noqa

import click
import toml
from urllib.parse import urljoin

from shub.config import SH_IMAGES_REGISTRY, list_targets_callback, load_shub_config
from shub.exceptions import BadParameterException, NotFoundException, ShubException, SubcommandException
from shub.image.upload import upload_cmd
from shub.utils import (create_default_setup_py, create_scrapinghub_yml_wizard,
                        find_exe, inside_project, make_deploy_request,
                        remember_cwd, run_cmd, run_python, STDOUT_ENCODING)

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

To avoid bundling gitignored or otherwise untracked files, you can build the
egg from a clean git checkout of HEAD instead of the working directory:

    shub deploy --clean-repo
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
@click.option("--clean-repo", is_flag=True,
              help="Build the egg from a clean git checkout of HEAD (via "
                   "`git archive`) instead of the working directory, so that "
                   "gitignored and other untracked files are not bundled "
                   "into the deploy. Can also be enabled via the 'clean_repo' "
                   "scrapinghub.yml option.")
def cli(target, version, debug, egg, build_egg, verbose, keep_log,
        ignore_size, clean_repo):
    conf, image = load_shub_config(), None
    if not build_egg:
        create_scrapinghub_yml_wizard(conf, target=target)
    image = conf.get_target_conf(target).image
    if not image:
        deploy_cmd(target, version, debug, egg, build_egg, verbose, keep_log,
                   conf=conf, clean_repo=clean_repo)
    elif image.startswith(SH_IMAGES_REGISTRY):
        upload_cmd(target, version)
    else:
        raise BadParameterException(
            "Please use `shub image` commands to work with Docker registries "
            "other than Scrapinghub default registry.")


def deploy_cmd(target, version, debug, egg, build_egg, verbose, keep_log,
               conf=None, clean_repo=False):
    tmpdir = None
    conf = conf or load_shub_config()
    clean_repo = clean_repo or conf.get_target_conf(
        target, auth_required=False).clean_repo
    try:
        if build_egg:
            egg, tmpdir = _build_egg(clean_repo=clean_repo)
            click.echo("Writing egg to %s" % build_egg)
            shutil.copyfile(egg, build_egg)
        else:
            targetconf = conf.get_target_conf(target)
            version = version or targetconf.version
            auth = (targetconf.apikey, '')

            if egg:
                click.echo("Using egg: %s" % egg)
                egg = egg
            else:
                click.echo("Packing version %s" % version)
                egg, tmpdir = _build_egg(clean_repo=clean_repo)

            _upload_egg(targetconf.endpoint, egg, targetconf.project_id,
                        version, auth, verbose, keep_log, targetconf.stack,
                        targetconf.requirements_file, targetconf.eggs, tmpdir)
            click.echo("Run your spiders at: "
                       "https://app.zyte.com/p/%s/"
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
    except OSError as e:
        raise ShubException(f"{e.strerror} {e.filename}")
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
        with open('Pipfile.lock', encoding='utf-8') as f:
            pipefile = json.load(f)
            deps = pipefile['default']
            sources_list = prepare_pip_source_args(pipefile['_meta']['sources'])
            sources = ' '.join(sources_list)
    except OSError:
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
    # Keep compatible with pipenv>=v2023.10.24
    elif isinstance(_requirements, dict):
        tmp.write('\n'.join(_requirements.values()).encode('utf-8'))
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


def _get_poetry_requirements_fallback():
    data = toml.load('poetry.lock')
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


def _get_poetry_requirements():
    executable = shutil.which("poetry")
    if executable is None:
        try:
            return _get_poetry_requirements_fallback()
        except Exception:
            raise NotFoundException("poetry executable not found.")
    try:
        return run_cmd([executable, "export", "--without-hashes", "-f", "requirements.txt"])
    except SubcommandException as original_exception:
        try:
            return _get_poetry_requirements_fallback()
        except Exception:
            raise original_exception


def _build_egg(clean_repo=False):
    if not inside_project():
        raise NotFoundException("No Scrapy project found in this location.")
    if clean_repo:
        return _build_egg_from_clean_repo()
    return _build_egg_in_cwd()


def _build_egg_in_cwd():
    create_default_setup_py()
    d = tempfile.mkdtemp(prefix="shub-deploy-")
    run_python(['setup.py', 'clean', '-a', 'bdist_egg', '-d', d])
    egg = glob.glob(os.path.join(d, '*.egg'))[0]
    return egg, d


def _build_egg_from_clean_repo():
    """
    Export the current git repository's HEAD commit to a temporary directory
    via `git archive`, then build the egg from there instead of the working
    directory.

    This keeps gitignored and other untracked files out of the deploy. Note
    that only committed changes are included: uncommitted local modifications
    are not part of the resulting egg.
    """
    git = find_exe('git')
    try:
        repo_root = run_cmd([git, 'rev-parse', '--show-toplevel'])
    except SubcommandException:
        raise NotFoundException(
            "--clean-repo (or the 'clean_repo' option) was used, but the "
            "current directory does not look like a git repository.")
    # Resolve symlinks on both sides (e.g. macOS' /tmp -> /private/tmp) so the
    # relative path is computed correctly.
    rel_project_dir = os.path.relpath(os.path.realpath(os.getcwd()),
                                      os.path.realpath(repo_root))
    clean_repo_dir = tempfile.mkdtemp(prefix="shub-deploy-clean-repo-")
    archive_path = os.path.join(clean_repo_dir, 'HEAD.tar')
    try:
        with open(archive_path, 'wb') as archive_file:
            subprocess.run(
                [git, 'archive', '--format=tar', 'HEAD'], cwd=repo_root,
                stdout=archive_file, stderr=subprocess.PIPE, check=True,
            )
        with tarfile.open(archive_path) as tar:
            # No extraction filter: the archive is generated by us from the
            # user's own repository, not untrusted input. The `filter`
            # keyword also isn't available on every Python 3.10 patch
            # release (it was backported to 3.10.12+ via PEP 706), and older
            # patch releases are still in use on some platforms.
            tar.extractall(clean_repo_dir)
        os.remove(archive_path)
        with remember_cwd():
            os.chdir(os.path.join(clean_repo_dir, rel_project_dir))
            return _build_egg_in_cwd()
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b'').decode(STDOUT_ENCODING, errors='replace')
        raise SubcommandException(
            "Error while calling 'git archive': %s\n\n%s" % (e, stderr))
    finally:
        shutil.rmtree(clean_repo_dir, ignore_errors=True)
