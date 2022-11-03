from __future__ import absolute_import

import contextlib
import datetime
import errno
import json
import os
import re
import subprocess
import sys
import time
from collections import deque
from configparser import ConfigParser
from distutils.spawn import find_executable
from distutils.version import LooseVersion, StrictVersion
from glob import glob
from importlib import import_module
from tempfile import NamedTemporaryFile, TemporaryFile
from urllib.parse import urljoin

import click
import pip
import requests
import setuptools  # noqa: F401
import yaml
from scrapinghub import ScrapinghubClient, ScrapinghubAPIError, HubstorageClient

# https://github.com/scrapinghub/shub/pull/309#pullrequestreview-113977920
try:
    from pip import main as pip_main
except:  # noqa
    try:
        # For pip v20: https://tinyurl.com/pip20-error
        from pip._internal.cli.main import pip_main
    except ImportError:
        try:
            # For pip v9 and v10: https://tinyurl.com/y8mvl8rb
            from pip._internal.main import main as pip_main
        except ImportError:
            from pip._internal import main as pip_main

import shub
from shub.compat import to_native_str
from shub.exceptions import (
    BadParameterException, InvalidAuthException, NotFoundException,
    RemoteErrorException, SubcommandException, DeployRequestTooLargeException,
    print_warning,
)


SCRAPY_CFG_FILE = os.path.expanduser("~/.scrapy.cfg")
FALLBACK_ENCODING = 'utf-8'
STDOUT_ENCODING = sys.stdout.encoding or FALLBACK_ENCODING
LAST_N_LOGS = 30

# 50MB for a whole request, reserve 5KB for meta info (e.g. headers)
REQUEST_FILES_SIZE_LIMIT = 50 * 1024 * 1024 - 5 * 1024

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


@contextlib.contextmanager
def remember_cwd():
    current_dir = os.getcwd()
    try:
        yield
    finally:
        os.chdir(current_dir)


def get_scrapinghub_client_from_config(conf):
    return ScrapinghubClient(
        conf.apikey, dash_endpoint=conf.endpoint
    )


def create_default_setup_py(**kwargs):
    closest = closest_file('scrapy.cfg')
    with remember_cwd():
        os.chdir(os.path.dirname(closest))
        if not os.path.exists('setup.py'):
            if 'settings' not in kwargs:
                kwargs['settings'] = get_config().get('settings', 'default')
            with open('setup.py', 'w') as f:
                f.write(_SETUP_PY_TEMPLATE % kwargs)
            click.echo("Created setup.py at {}".format(os.getcwd()))


def make_deploy_request(url, data, files, auth, verbose, keep_log):
    _check_deploy_files_size(files)
    last_logs = deque(maxlen=LAST_N_LOGS)
    try:
        rsp = requests.post(url=url, auth=auth, data=data, files=files,
                            stream=True, timeout=300)
        rsp.raise_for_status()
        write_and_echo_logs(keep_log, last_logs, rsp, verbose)
        return True
    except requests.HTTPError as exc:
        rsp = exc.response

        if rsp.status_code == 403:
            raise InvalidAuthException

        try:
            error = rsp.json()['message']
            if 'Traceback' in error:
                error = ('\n---------- REMOTE TRACEBACK ----------\n' + error +
                         '\n---------- END OF REMOTE TRACEBACK ----------')
        except (ValueError, TypeError, KeyError):
            error = rsp.text or "Status %d" % rsp.status_code
        msg = "Deploy failed ({}):\n{}".format(rsp.status_code, error)
        raise RemoteErrorException(msg)
    except requests.RequestException as exc:
        raise RemoteErrorException("Deploy failed: {}".format(exc))


def _check_deploy_files_size(files):
    """Ensure that request's files total size is less than current limit."""
    ctx = click.get_current_context(silent=True)
    if not isinstance(files, list) or ctx and ctx.params.get('ignore-size'):
        return
    files_size = sum(
        len(fp) if isinstance(fp, str)
        else os.fstat(fp.fileno()).st_size
        for (fname, fp) in files
    )
    if files_size > REQUEST_FILES_SIZE_LIMIT:
        raise DeployRequestTooLargeException


def write_and_echo_logs(keep_log, last_logs, rsp, verbose):
    """It will write logs to temporal file and echo if verbose is True."""
    with NamedTemporaryFile(prefix='shub_deploy_', suffix='.log',
                            delete=(not keep_log)) as log_file:
        for line in rsp.iter_lines():
            if verbose:
                click.echo(line)
            last_logs.append(line)
            log_file.write(line + b'\n')

        deployed = _is_deploy_successful(last_logs)
        echo_short_log_if_deployed(deployed, last_logs, log_file, verbose)
        if not log_file.delete:
            click.echo("Deploy log location: %s" % log_file.name)
        if not deployed:
            try:
                last_log = last_logs[-1]
            except IndexError:
                last_log = "(No log messages)"
            raise RemoteErrorException("Deploy failed: {}".format(last_log))


def echo_short_log_if_deployed(deployed, last_logs, log_file, verbose):
    if deployed:
        if not verbose:
            click.echo(last_logs[-1])
    else:
        log_file.delete = False
        if not verbose:
            click.echo("Deploy log last %s lines:" % len(last_logs))
            for line in last_logs:
                click.echo(line)


def _is_deploy_successful(last_logs):
    try:
        data = json.loads(to_native_str(last_logs[-1]))
        if 'status' in data and data['status'] == 'ok':
            return True
    except Exception:
        pass


@contextlib.contextmanager
def patch_sys_executable():
    """
    Context manager that monkey-patches sys.executable to point to the Python
    interpreter.

    Some scripts, in particular pip, depend on sys.executable pointing to the
    Python interpreter. When frozen, however, sys.executable points to the
    stand-alone file (i.e. the frozen script).
    """
    if getattr(sys, 'frozen', False):
        orig_exe = sys.executable
        py_exe = find_exe('python')
        # PyInstaller sets this environment variable in its bootloader. Remove
        # it so the system-wide Python installation uses its own library path
        # (this is particularly important if the system Python version differs
        # from the Python version that the binary was compiled with)
        orig_lib_path = os.environ.pop('LD_LIBRARY_PATH', None)
        sys.executable = py_exe
        yield
        sys.executable = orig_exe
        if orig_lib_path:
            os.environ['LD_LIBRARY_PATH'] = orig_lib_path
    else:
        yield


def find_exe(exe_name):
    exe = find_executable(exe_name)
    if not exe:
        raise NotFoundException("Please install {}".format(exe_name))
    return exe


def run_cmd(*args, **kwargs):
    """Run a command and return its output, decoded by the stdout encoding and
    stripped of trailing newlines. `args` and `kwargs` are forwarded to
    `subprocess.check_output`.

    Raises SubcommandException on non-zero exit codes or other subprocess
    errors."""
    def _clean(s):
        return s.decode(STDOUT_ENCODING).replace(os.linesep, '\n').strip('\n')

    with TemporaryFile() as tmpfile:
        kwargs.setdefault('stderr', tmpfile)
        try:
            return _clean(subprocess.check_output(*args, **kwargs))
        except subprocess.CalledProcessError as e:
            msg = ("Error while calling subcommand: %s\n\nCOMMAND OUTPUT\n"
                   "--------------\n%s" % (e, _clean(e.output)))
            tmpfile.seek(0)
            e.stderr = _clean(tmpfile.read())
            if e.stderr:
                msg += "\n\nSTDERR\n------\n%s" % e.stderr
            raise SubcommandException(msg)


def pwd_version():
    """
    Try to find version information on whatever lives in the current directory
    -- most commonly a Python package or Scrapy project -- by trying (in this
    order):
        - git commit/branch
        - mercurial commit/branch
        - bazaar commit/branch
        - setup.py in this folder
        - setup.py next to closest scrapy.cfg
    If none of these work, fall back to the UNIX time.
    """
    ver = pwd_git_version()
    if not ver:
        ver = pwd_hg_version()
    if not ver:
        ver = pwd_bzr_version()
    if not ver and os.path.isfile('setup.py'):
        ver = _last_line_of(run_python(['setup.py', '--version']))
    if not ver:
        closest_scrapycfg = closest_file('scrapy.cfg')
        if closest_scrapycfg:
            setuppy = os.path.join(os.path.dirname(closest_scrapycfg),
                                   'setup.py')
            if os.path.isfile(setuppy):
                ver = _last_line_of(run_python([setuppy, '--version']))
    if not ver:
        ver = str(int(time.time()))
    ver = re.sub(r'[^\w.-]+', '', ver)
    return ver


def pwd_git_version():
    git = find_executable('git')
    if not git:
        return None
    try:
        commit_id = run_cmd([git, 'describe', '--always'])
    except SubcommandException:
        try:
            commit_id = run_cmd([git, 'rev-list', '--count', 'HEAD'])
        except SubcommandException:
            return None
    branch = run_cmd([git, 'rev-parse', '--abbrev-ref', 'HEAD'])
    return '%s-%s' % (commit_id, branch)


def pwd_hg_version():
    hg = find_executable('hg')
    if not hg:
        return None
    try:
        commit_id = run_cmd([hg, 'tip', '--template', '{rev}'])
    except SubcommandException:
        return None
    branch = run_cmd([hg, 'branch'])
    return 'r%s-%s' % (commit_id, branch)


def pwd_bzr_version():
    bzr = find_executable('bzr')
    if not bzr:
        return None
    try:
        return '%s' % run_cmd([bzr, 'revno']).strip()
    except SubcommandException:
        return None


def run_python(cmd, *args, **kwargs):
    """
    Call Python interpreter with supplied list of arguments and return its
    output. `args` and `kwargs` are forwarded to `subprocess.check_output`.
    """
    with patch_sys_executable():
        return run_cmd([sys.executable] + cmd, *args, **kwargs)


def decompress_egg_files(directory=None):
    try:
        EXTS = pip.utils.ARCHIVE_EXTENSIONS
    except AttributeError:
        try:
            EXTS = pip._internal.utils.misc.ARCHIVE_EXTENSIONS
        except AttributeError:
            EXTS = ('.zip', '.whl', '.tar', '.tar.gz', '.tar.bz2')
    try:
        unpack_file = pip.utils.unpack_file
    except AttributeError:
        # XXX a work-around for pip >= 10.0
        try:
            unpack_file = pip.util.unpack_file
        except AttributeError:
            try:
                unpack_file = pip._internal.utils.misc.unpack_file
            except AttributeError:
                from pip._internal.utils.unpacking import unpack_file
    pathname = "*"
    if directory is not None:
        pathname = os.path.join(directory, pathname)
    eggs = [f for ext in EXTS for f in glob(pathname + "%s" % ext)]
    if not eggs:
        files = glob(pathname)
        err = ('No egg files with a supported file extension were found. '
               'Files: %s' % ', '.join(files))
        raise NotFoundException(err)
    for egg in eggs:
        click.echo("Uncompressing: %s" % egg)
        egg_ext = EXTS[list(egg.endswith(ext) for ext in EXTS).index(True)]
        decompress_location = egg[:-len(egg_ext)]
        try:
            unpack_file(egg, decompress_location, None)
        except TypeError:
            unpack_file(egg, decompress_location, None, None)


def build_and_deploy_eggs(project, endpoint, apikey):
    egg_dirs = (f for f in glob('*') if os.path.isdir(f))

    for egg_dir in egg_dirs:
        os.chdir(egg_dir)
        build_and_deploy_egg(project, endpoint, apikey)
        os.chdir('..')


def build_and_deploy_egg(project, endpoint, apikey):
    """Builds and deploys the current dir's egg"""
    click.echo("Building egg in: %s" % os.getcwd())
    try:
        run_python(['setup.py', 'bdist_egg'])
    except SubcommandException:
        # maybe a C extension or distutils package, forcing bdist_egg
        click.echo("Couldn't build an egg with vanilla setup.py, trying with "
                   "setuptools...")
        script = "import setuptools; __file__='setup.py'; execfile('setup.py')"
        run_python(['-c', script, 'bdist_egg'])

    _deploy_dependency_egg(project, endpoint, apikey)


def _deploy_dependency_egg(project, endpoint, apikey, name=None, version=None, egg_info=None):
    name = name or _get_dependency_name()
    version = version or pwd_version()
    egg_info = egg_info or _get_egg_info(name)
    egg_name, egg_path = egg_info
    url = urljoin(endpoint, 'eggs/add.json')
    data = {'project': project, 'name': name, 'version': version}
    auth = (apikey, '')

    click.echo('Deploying dependency {} {} to Scrapy Cloud project {}'.format(name, version, project))

    with open(egg_path, 'rb') as egg_fp:
        files = {'egg': (egg_name, egg_fp)}
        make_deploy_request(url, data, files, auth, False, False)

    success = "Deployed eggs list at: https://app.scrapinghub.com/p/%s/deploy/"
    click.echo(success % project)


def _last_line_of(s):
    return s.split('\n')[-1]


def _get_dependency_name():
    # In some cases, python setup.py --name returns more than one line, so we
    # use the last one to get the name
    return _last_line_of(run_python(['setup.py', '--name']))


def _get_egg_info(name):
    egg_filename = name.replace('-', '_')
    egg_path_glob = os.path.join('dist', '%s*' % egg_filename)
    egg_path = glob(egg_path_glob)[0]
    return egg_filename, egg_path


def get_job_specs(job):
    """
    Parse job identifier into valid job id and corresponding API key.

    With projects default=10 and external=20 defined in config:
    * 1/1 -> 10/1/1
    * 2/2/2 -> 2/2/2
    * external/2/2 -> 20/2/2

    It also accepts job URLs from Scrapinghub.
    """
    match = re.match(r'^((\w+)/)?(\d+/\d+)$', job)
    if not match:
        job_url_re = r'^https?://[^/]+/p/((\d+)/)(?:job/)?(\d+/\d+).*'
        match = re.match(job_url_re, job)
    if not match:
        raise BadParameterException(
            "Job ID {} is invalid. Format should be spiderid/jobid (inside a "
            "project) or target/spiderid/jobid, where target can be either a "
            "project ID or an identifier defined in scrapinghub.yml."
            "".format(job),
            param_hint='job_id',
        )
    # XXX: Lazy import due to circular dependency
    from shub.config import get_target_conf
    targetconf = get_target_conf(match.group(2) or 'default')
    return ("{}/{}".format(targetconf.project_id, match.group(3)),
            targetconf.apikey)


def get_job(job):
    jobid, apikey = get_job_specs(job)
    hsc = HubstorageClient(auth=apikey)
    job = hsc.get_job(jobid)
    if not job.metadata:
        raise NotFoundException('Job {} does not exist'.format(jobid))
    return job


def closest_file(filename, path='.', prevpath=None):
    """
    Return the path to the closest file with the given filename by traversing
    the current directory and its parents
    """
    if path == prevpath:
        return None
    path = os.path.abspath(path)
    thisfile = os.path.join(path, filename)
    if os.path.exists(thisfile):
        return thisfile
    return closest_file(filename, os.path.dirname(path), path)


def inside_project():
    scrapy_module = os.environ.get('SCRAPY_SETTINGS_MODULE')
    if scrapy_module is not None:
        try:
            import_module(scrapy_module)
        except ImportError as exc:
            print_warning("Cannot import scrapy settings module %s: %s"
                          "" % (scrapy_module, exc))
        else:
            return True
    return bool(closest_file('scrapy.cfg'))


def get_config(use_closest=True):
    """Get Scrapy config file as a ConfigParser"""
    sources = get_sources(use_closest)
    cfg = ConfigParser()
    cfg.read(sources)
    return cfg


def get_sources(use_closest=True):
    xdg_config_home = os.environ.get('XDG_CONFIG_HOME') or \
        os.path.expanduser('~/.config')
    sources = ['/etc/scrapy.cfg', r'c:\scrapy\scrapy.cfg',
               xdg_config_home + '/scrapy.cfg',
               os.path.expanduser('~/.scrapy.cfg')]
    if use_closest:
        closest_scrapy_cfg_path = closest_file('scrapy.cfg')
        if closest_scrapy_cfg_path:
            sources.append(closest_scrapy_cfg_path)
    return sources


def get_scrapycfg_targets(cfgfiles=None):
    cfg = ConfigParser()
    cfg.read(cfgfiles or [])
    baset = dict(cfg.items('deploy')) if cfg.has_section('deploy') else {}
    targets = {}
    targets['default'] = baset
    for x in cfg.sections():
        if x.startswith('deploy:'):
            t = baset.copy()
            t.update(cfg.items(x))
            targets[x[7:]] = t
    for tname, t in list(targets.items()):
        try:
            int(t.get('project', 0))
        except ValueError:
            # Don't import non-numeric project IDs, and also throw away the
            # URL and credentials associated with these projects (since the
            # project ID does not belong to SH, neither do the endpoint or the
            # auth information)
            del targets[tname]
        if t.get('url', "").endswith('scrapyd/'):
            t['url'] = t['url'][:-8]
    targets.setdefault('default', {})
    return targets


def job_live(job, refresh_meta_after=60):
    """
    Check whether job is in 'pending' or 'running' state. If job metadata was
    fetched longer than `refresh_meta_after` seconds ago, refresh it.
    """
    if not hasattr(job, '_metadata_updated'):
        # Assume just loaded
        job._metadata_updated = time.time()
    if time.time() - job._metadata_updated > refresh_meta_after:
        job.metadata.expire()
        # Fetching actually happens on job.metadata['state'], but close enough
        job._metadata_updated = time.time()
    return job.metadata['state'] in ('pending', 'running')


def job_resource_iter(job, resource, output_json=False, follow=True,
                      tail=None):
    """
    Given a python-hubstorage job and resource (e.g. job.items), return a
    generator that periodically checks the job resource and yields its items.
    The generator will exit when the job has finished.

    As a handy shortcut, iter_func will be iterated through only once if
    `follow` is set to `False`.
    """
    last_item_key = None
    if tail is not None:
        total_nr_items = resource.stats()['totals']['input_values']
        # This is the last entry to be skipped, i.e. it will NOT be displayed
        last_item = total_nr_items - tail - 1
        if last_item >= 0:
            last_item_key = '{}/{}'.format(job.key, last_item)
    if not job_live(job):
        follow = False
    resource_iter = resource.iter_json if output_json else resource.iter_values
    if not follow:
        for item in resource_iter(startafter=last_item_key):
            yield item
        return
    while True:
        # XXX: Always use iter_json until Kumo team fixes iter_values to also
        # return '_key'
        for json_line in resource.iter_json(startafter=last_item_key):
            item = json.loads(json_line)
            last_item_key = item['_key']
            yield json_line if output_json else item
        if not job_live(job):
            break
        # Workers only upload data to hubstorage every 15 seconds
        time.sleep(15)


def latest_github_release(force_update=False, timeout=1., cache=None):
    """
    Get GitHub data for latest shub release. If it was already requested today,
    return a cached version unless ``force_update`` is set to ``True``.
    """
    REQ_URL = "https://api.github.com/repos/scrapinghub/shub/releases/latest"
    cache = cache or os.path.join(click.get_app_dir('scrapinghub'),
                                  'last_release.txt')
    today = datetime.date.today().toordinal()
    if not force_update and os.path.isfile(cache):
        with open(cache, 'r') as f:
            try:
                release_data = json.load(f)
            except Exception:
                release_data = {}
        # Check for equality (and not smaller or equal) so we don't get thrown
        # off track if the clock was ever misconfigured and a future date was
        # saved
        if release_data.get('_shub_last_update', 0) == today:
            return release_data
    release_data = requests.get(REQ_URL, timeout=timeout).json()
    release_data['_shub_last_update'] = today
    try:
        shubdir = os.path.dirname(cache)
        try:
            os.makedirs(shubdir)
        except OSError:
            if not os.path.isdir(shubdir):
                raise
        with open(cache, 'w') as f:
            json.dump(release_data, f)
    except Exception:
        pass
    return release_data


def update_available(silent_fail=True):
    """
    Check whether most recent GitHub release of shub is newer than the shub
    version in use. If a newer version is available, return a link to the
    release on GitHub, otherwise return ``None``.
    """
    try:
        release_data = latest_github_release()
        latest_rls = StrictVersion(release_data['name'].lstrip('v'))
        used_rls = StrictVersion(shub.__version__)
        if used_rls >= latest_rls:
            return None
        return release_data['html_url']
    except Exception:
        if not silent_fail:
            raise
        # Don't let this interfere with shub usage
        return None


def download_from_pypi(dest, pkg=None, reqfile=None, extra_args=None):
    if (not pkg and not reqfile) or (pkg and reqfile):
        raise ValueError('Call with either pkg or reqfile')
    extra_args = extra_args or []
    pip_version = LooseVersion(getattr(pip, '__version__', '1.0'))
    cmd = 'install'
    no_wheel = []
    target = [pkg] if pkg else ['-r', reqfile]
    if pip_version >= LooseVersion('1.4'):
        no_wheel = ['--no-use-wheel']
    if pip_version >= LooseVersion('7'):
        no_wheel = ['--no-binary=:all:']
    if pip_version >= LooseVersion('8'):
        cmd = 'download'
    with patch_sys_executable():
        pip_main([cmd, '-d', dest, '--no-deps'] + no_wheel + extra_args +
                 target)


@contextlib.contextmanager
def update_yaml_dict(conf_path=None):
    """
    Context manager for updating a YAML file. Key ordering and comments are not
    preserved.
    """
    if not conf_path:
        click.secho("Using update_yaml_dict without path is deprecated. Import"
                    " GLOBAL_SCRAPINGHUB_YML_PATH from shub.config",
                    fg='yellow')
        from shub.config import GLOBAL_SCRAPINGHUB_YML_PATH
        conf_path = GLOBAL_SCRAPINGHUB_YML_PATH
    try:
        with open(conf_path, 'r') as f:
            conf = yaml.safe_load(f) or {}
    except IOError as e:
        if e.errno != errno.ENOENT:
            raise
        conf = {}
    # Code inside context manager is executed after this yield
    yield conf
    # Avoid writing "key: {}"
    for key in list(conf):
        if conf[key] == {}:
            del conf[key]
    with open(conf_path, 'w') as f:
        # Avoid writing "{}"
        if conf:
            yaml.safe_dump(conf, f, default_flow_style=False)


def has_project_access(project, endpoint, apikey):
    """Check whether an API key has access to a given project. May raise
    InvalidAuthException if the API key is invalid (but not if it is valid but
    lacks access to the project)"""
    client = ScrapinghubClient(apikey, dash_endpoint=endpoint)
    try:
        return project in client.projects.list()
    except ScrapinghubAPIError as e:
        if 'Authentication failed' in str(e):
            raise InvalidAuthException
        else:
            raise RemoteErrorException(str(e))


def get_project_dir():
    """Get the path to the closest directory that contains either
    ``scrapinghub.yml``. ``scrapy.cfg``, or ``Dockerfile`` (in this priority).
    """
    for filename in ['scrapinghub.yml', 'scrapy.cfg', 'Dockerfile']:
        closest = closest_file(filename)
        if closest:
            return os.path.dirname(closest)
    raise NotFoundException(
        "Cannot find project: There is no scrapinghub.yml, scrapy.cfg, or "
        "Dockerfile in this directory or any of the parent directories.")


def _get_target_project(conf, target):
    """Ask for project ID (or use given target if numerical) and confirm that
    user is logged in and has project access"""
    # Will raise MissingAuthException if user is not logged in
    endpoint, apikey = conf.get_endpoint(0), conf.get_apikey(0)
    if target.isdigit():
        project = int(target)
        target = 'default'
    else:
        project = click.prompt("Target project ID", type=int)
    if not has_project_access(project, endpoint, apikey):
        raise InvalidAuthException(
            "The account you logged in to has no access to project {}. "
            "Please double-check the project ID and make sure you logged "
            "in to the correct acount.".format(project),
        )
    return target, project


def _detect_custom_image_project():
    """Guess if the user may want to deploy a custom image based on the
    existence of ``scrapy.cfg`` and ``Dockerfile``. If there are both, ask."""
    project_dir = get_project_dir()
    has_scrapy_cfg = os.path.exists(os.path.join(project_dir, 'scrapy.cfg'))
    has_dockerfile = os.path.exists(os.path.join(project_dir, 'Dockerfile'))
    if has_scrapy_cfg and has_dockerfile:
        return click.confirm(
            "You have a Dockerfile in your project directory. Would you like "
            "to deploy it as custom image?", default=True)
    elif has_dockerfile:
        return True
    return False


def _update_conf(conf, target, project, repository):
    """Update configuration target with given ``project`` and ``repository``"""
    if project:
        # XXX: Save {'id': project} once we normalize project config on loading
        conf.projects[target] = project
    if repository:
        if target == 'default':
            conf.images[target] = repository
        else:
            # XXX: Remove once we normalize project config on loading
            if not isinstance(conf.projects[target], dict):
                conf.projects[target] = {'id': conf.projects[target]}
            conf.projects[target]['image'] = repository


def _update_conf_file(filename, target, project, repository):
    """Load the given config file, update ``target`` with the given ``project``
    and ``repository``, then save it. If the file does not exist, it will be
    created."""
    try:
        # XXX: Runtime import to avoid circular dependency
        from shub.config import ShubConfig
        conf = ShubConfig()
        if os.path.exists(filename):
            conf.load_file(filename)
        _update_conf(conf, target, project, repository)
        conf.save(filename)
    except Exception as e:
        click.echo(
            "There was an error while trying to write to %s: %s"
            "" % (filename, e),
        )
    else:
        click.echo("Saved to %s." % filename)


class _AnyParamType(click.ParamType):
    name = "any"

    def convert(self, value, param, ctx):
        return value


def create_scrapinghub_yml_wizard(conf, target='default', image=None):
    """
    Ask user for project ID, ensure they have access to that project, and save
    it in the local ``scrapinghub.yml``.

    If ``image`` is ``True``, the user will also be asked for the image
    repository to use. If ``image`` is ``None``, the wizard will ask for a
    repository if ``Dockerfile`` exists.

    The wizard will only ever ask questions and touch the configuration if at
    least one of these two conditions is met:

        1. There is no local scrapinghub.yml
        2. ``image`` is ``True``, and the given ``target`` is defined but has
           no image repository configured; this will happen when transitioning
           a previously stack-based project to a custom image-based one, i.e.
           when you already have a ``scrapinghub.yml`` but now run ``shub image
           build`` for the first time

    In all other cases, the wizard will return without asking questions and
    without altering ``conf``.
    """
    closest_sh_yml = os.path.join(get_project_dir(), 'scrapinghub.yml')
    run_wizard = (
        not os.path.exists(closest_sh_yml) or
        (image and target in conf.projects
            and not conf.get_target_conf(target).image)
    )
    if not run_wizard:
        return
    project = None
    repository = None
    if target not in conf.projects and 'default' not in conf.projects:
        target, project = _get_target_project(conf, target)
        if target == 'default':
            click.echo(
                "Saving project %d as default target. You can deploy to it "
                "via 'shub deploy' from now on" % project)
        else:
            click.echo(
                "Saving project %d as target '%s'. You can deploy to it via "
                "'shub deploy %s' from now on" % (project, target, target))
    if image or (image is None and _detect_custom_image_project()):
        repository = click.prompt(
            "Image repository (leave empty to use Scrapinghub's repository)",
            default=True, show_default=False, type=_AnyParamType())
    _update_conf(conf, target, project, repository)
    _update_conf_file(closest_sh_yml, target, project, repository)
