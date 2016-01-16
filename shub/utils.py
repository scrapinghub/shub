from __future__ import unicode_literals, absolute_import
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
from ConfigParser import SafeConfigParser
from distutils.spawn import find_executable
from distutils.version import StrictVersion
from glob import glob
from importlib import import_module
from tempfile import NamedTemporaryFile
from six.moves.urllib.parse import urljoin
from subprocess import Popen, PIPE, CalledProcessError

import click
import requests

from hubstorage import HubstorageClient

import shub
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
        with NamedTemporaryFile(prefix='shub_deploy_', suffix='.log',
                                delete=(not keep_log)) as log_file:
            for line in rsp.iter_lines():
                if verbose:
                    click.echo(line)
                last_logs.append(line)
                log_file.write(line + '\n')
            if _is_deploy_successful(last_logs):
                if not verbose:
                    click.echo(last_logs[-1])
            else:
                log_file.delete = False
                if not verbose:
                    click.echo("Deploy log last %s lines:" % len(last_logs))
                    for line in last_logs:
                        click.echo(line)
            if not log_file.delete:
                click.echo("Deploy log location: %s" % log_file.name)
        return True
    except requests.HTTPError as exc:
        rsp = exc.response

        if rsp.status_code == 403:
            raise InvalidAuthException

        msg = "Deploy failed ({}):\n{}".format(rsp.status_code, rsp.text)
        raise RemoteErrorException(msg)
    except requests.RequestException as exc:
        raise RemoteErrorException("Deploy failed: {}".format(exc))


def _is_deploy_successful(last_logs):
    try:
        data = json.loads(last_logs[-1])
        if 'status' in data and data['status'] == 'ok':
            return True
    except Exception:
        pass


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
        ver = _last_line_of(run('python setup.py --version'))
    if not ver:
        closest_scrapycfg = closest_file('scrapy.cfg')
        if closest_scrapycfg:
            setuppy = os.path.join(os.path.dirname(closest_scrapycfg),
                                   'setup.py')
            if os.path.isfile(setuppy):
                ver = _last_line_of(run('python {} --version'.format(setuppy)))
    if not ver:
        ver = str(int(time.time()))
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


def run(cmd):
    output = subprocess.check_output(cmd, shell=True)
    return output.decode(STDOUT_ENCODING).strip()


def decompress_egg_files():
    decompressor_by_ext = _build_decompressor_by_ext_map()
    eggs = [f for ext in decompressor_by_ext for f in glob('*.%s' % ext)]

    if not eggs:
        files = glob('*')
        err = ('No egg files with a supported file extension were found. '
               'Files: %s' % ', '.join(files))
        raise NotFoundException(err)

    for egg in eggs:
        click.echo("Uncompressing: %s" % egg)
        run("%s %s" % (decompressor_by_ext[_ext(egg)], egg))


def build_and_deploy_eggs(project, endpoint, apikey):
    egg_dirs = (f for f in glob('*') if os.path.isdir(f))

    for egg_dir in egg_dirs:
        os.chdir(egg_dir)
        build_and_deploy_egg(project, endpoint, apikey)
        os.chdir('..')


def _build_decompressor_by_ext_map():
    unzip = 'unzip -q'

    return {'zip': unzip,
            'whl': unzip,
            'bz2': 'tar jxf',
            'gz': 'tar zxf'}


def _ext(file_path):
    return os.path.splitext(file_path)[1].strip('.')


def build_and_deploy_egg(project, endpoint, apikey):
    """Builds and deploys the current dir's egg"""
    click.echo("Building egg in: %s" % os.getcwd())
    try:
        run('python setup.py bdist_egg')
    except CalledProcessError:
        # maybe a C extension or distutils package, forcing bdist_egg
        click.echo("Couldn't build an egg with vanilla setup.py, trying with setuptools...")
        run('python -c  "import setuptools; __file__=\'setup.py\'; execfile(\'setup.py\')" bdist_egg')

    _deploy_dependency_egg(project, endpoint, apikey)


def _deploy_dependency_egg(project, endpoint, apikey):
    name = _get_dependency_name()
    version = pwd_version()
    egg_name, egg_path = _get_egg_info(name)

    url = urljoin(endpoint, 'eggs/add.json')
    data = {'project': project, 'name': name, 'version': version}
    auth = (apikey, '')

    click.echo('Deploying dependency to Scrapy Cloud project "%s"' % project)

    with open(egg_path, 'rb') as egg_fp:
        files = {'egg': (egg_name, egg_fp)}
        make_deploy_request(url, data, files, auth, False, False)

    success = "Deployed eggs list at: https://dash.scrapinghub.com/p/%s/eggs"
    click.echo(success % project)


def _last_line_of(s):
    return s.split('\n')[-1]


def _get_dependency_name():
    # In some cases, python setup.py --name returns more than one line, so we use the last one to get the name
    return _last_line_of(run('python setup.py --name'))


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
    """
    match = re.match(r'^((\w+)/)?(\d+/\d+)$', job)
    if not match:
        raise BadParameterException(
            "Job ID {} is invalid. Format should be spiderid/jobid (inside a "
            "project) or target/spiderid/jobid, where target can be either a "
            "project ID or an identifier defined in scrapinghub.yml."
            "".format(job),
            param='job_id',
        )
    # XXX: Lazy import due to circular dependency
    from shub.config import get_target
    project_id, endpoint, apikey = get_target(match.group(2) or 'default')
    return "{}/{}".format(project_id, match.group(3)), apikey


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
    for t in targets.values():
        if t.get('url', "").endswith('scrapyd/'):
            t['url'] = t['url'][:-8]
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


def job_resource_iter(job, iter_func, follow=True, key_func=None):
    """
    Given a python-hubstorage job and resource generator (e.g.
    job.items.iter_json), return a generator that periodically checks the job
    resource generator and yields its items. The generator will exit when the
    job has finished.

    key_func should be a function which accepts an item from iter_func and
    returns its key. By default, the key is retrieved via
    json.loads(item)['_key'] (suitable for the iter_json iterators).

    As a handy shortcut, iter_func will be iterated through only once if
    `follow` is set to `False`.
    """
    if not job_live(job):
        follow = False
    if not follow:
        for item in iter_func():
            yield item
        return
    last_item_key = None
    key_func = key_func or (lambda item: json.loads(item)['_key'])
    while True:
        for item in iter_func(startafter=last_item_key):
            yield item
            last_item_key = key_func(item)
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
