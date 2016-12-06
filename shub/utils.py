from __future__ import absolute_import
import contextlib
import datetime
import errno
import json
import os
import subprocess
import sys
import re
import time
import warnings

from collections import deque
from six.moves.configparser import SafeConfigParser
from distutils.spawn import find_executable
from distutils.version import LooseVersion, StrictVersion
from glob import glob
from importlib import import_module
from tempfile import NamedTemporaryFile
from six.moves.urllib.parse import urljoin
from subprocess import Popen, PIPE, CalledProcessError

import click
import pip
import requests

try:
    from scrapinghub import HubstorageClient
except ImportError:
    # scrapinghub < 1.9.0
    from hubstorage import HubstorageClient

import shub
from shub.compat import to_native_str
from shub.exceptions import (BadParameterException, InvalidAuthException,
                             NotFoundException, RemoteErrorException)

SCRAPY_CFG_FILE = os.path.expanduser("~/.scrapy.cfg")
FALLBACK_ENCODING = 'utf-8'
STDOUT_ENCODING = sys.stdout.encoding or FALLBACK_ENCODING
LAST_N_LOGS = 30


def make_deploy_request(url, data, files, auth, verbose, keep_log):
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


def get_cmd(cmd):
    with open(os.devnull, 'wb') as null:
        return Popen(cmd, stdout=PIPE, stderr=null)


def get_cmd_output(cmd):
    process = get_cmd(cmd)
    return process.communicate()[0].decode(STDOUT_ENCODING)


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
    process = get_cmd([git, 'describe', '--always'])
    commit_id = process.communicate()[0].decode(STDOUT_ENCODING).strip('\n')
    if process.wait() != 0:
        commit_id = get_cmd_output([git, 'rev-list', '--count', 'HEAD']).strip('\n')
    if not commit_id:
        return None
    branch = get_cmd_output([git, 'rev-parse', '--abbrev-ref', 'HEAD']).strip('\n')
    return '%s-%s' % (commit_id, branch)


def pwd_hg_version():
    hg = find_executable('hg')
    if not hg:
        return None
    commit_id = get_cmd_output([hg, 'tip', '--template', '{rev}'])
    if not commit_id:
        return None
    branch = get_cmd_output([hg, 'branch']).strip('\n')
    return 'r%s-%s' % (commit_id, branch)


def pwd_bzr_version():
    bzr = find_executable('bzr')
    if not bzr:
        return None
    return '%s' % get_cmd_output([bzr, 'revno']).strip()


def run_python(args):
    """
    Call Python 2 interpreter with supplied list of arguments and return its
    output.
    """
    with patch_sys_executable():
        output = subprocess.check_output([sys.executable] + args)
        return output.decode(STDOUT_ENCODING).strip()


def decompress_egg_files(directory=None):
    try:
        EXTS = pip.utils.ARCHIVE_EXTENSIONS
    except AttributeError:
        EXTS = ('.zip', '.whl', '.tar', '.tar.gz', '.tar.bz2')
    try:
        unpack_file = pip.utils.unpack_file
    except AttributeError:
        unpack_file = pip.util.unpack_file
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
    except CalledProcessError:
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
    return (egg_filename, egg_path)


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
        job_url_re = r'^https?://[^/]+/p/((\d+)/)job/(\d+/\d+).*'
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


def retry_on_eintr(function, *args, **kw):
    """Run a function and retry it while getting EINTR errors"""
    while True:
        try:
            return function(*args, **kw)
        except IOError as e:
            if e.errno != errno.EINTR:
                raise


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
            warnings.warn("Cannot import scrapy settings module %s: %s"
                          "" % (scrapy_module, exc))
        else:
            return True
    return bool(closest_file('scrapy.cfg'))


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
        sources.append(closest_file('scrapy.cfg'))
    return sources


def get_scrapycfg_targets(cfgfiles=None):
    cfg = SafeConfigParser()
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
        pip.main([cmd, '-d', dest, '--no-deps'] + no_wheel + extra_args +
                 target)
