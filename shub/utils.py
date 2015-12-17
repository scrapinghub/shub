from __future__ import unicode_literals, absolute_import
import errno
import os
import subprocess
import sys
import re
import warnings

from ConfigParser import SafeConfigParser
from glob import glob
from importlib import import_module
from os import devnull
from os.path import isdir
from six.moves.urllib.parse import urljoin
from subprocess import Popen, PIPE, CalledProcessError

import requests

from click import ClickException
from hubstorage import HubstorageClient

from shub.click_utils import log
from shub.exceptions import AuthException

SCRAPY_CFG_FILE = os.path.expanduser("~/.scrapy.cfg")
FALLBACK_ENCODING = 'utf-8'
STDOUT_ENCODING = sys.stdout.encoding or FALLBACK_ENCODING


def make_deploy_request(url, data, files, auth):
    try:
        rsp = requests.post(url=url, auth=auth, data=data, files=files,
                            stream=True, timeout=300)
        rsp.raise_for_status()
        for line in rsp.iter_lines():
            log(line)
        return True
    except requests.HTTPError as exc:
        rsp = exc.response

        if rsp.status_code == 403:
            raise AuthException()

        msg = "Deploy failed ({}):\n{}".format(rsp.status_code, rsp.text)
        raise ClickException(msg)
    except requests.RequestException as exc:
        raise ClickException("Deploy failed: {}".format(exc))


# XXX: The next six should be refactored

def get_cmd(cmd):
    with open(devnull, 'wb') as null:
        return Popen(cmd, stdout=PIPE, stderr=null)


def get_cmd_output(cmd):
    process = get_cmd(cmd)
    return process.communicate()[0].decode(STDOUT_ENCODING)


def pwd_git_version():
    process = get_cmd(['git', 'describe', '--always'])
    commit_id = process.communicate()[0].decode(STDOUT_ENCODING).strip('\n')
    if process.wait() != 0:
        commit_id = get_cmd_output(['git', 'rev-list', '--count', 'HEAD']).strip('\n')

    if not commit_id:
        return None
    branch = get_cmd_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip('\n')
    return '%s-%s' % (commit_id, branch)


def pwd_hg_version():
    commit_id = get_cmd_output(['hg', 'tip', '--template', '{rev}'])
    if not commit_id:
        return None
    branch = get_cmd_output(['hg', 'branch']).strip('\n')
    return 'r%s-%s' % (commit_id, branch)


def pwd_bzr_version():
    return '%s' % get_cmd_output(['bzr', 'revno']).strip()


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
        raise ClickException(err)

    for egg in eggs:
        log("Uncompressing: %s" % egg)
        run("%s %s" % (decompressor_by_ext[_ext(egg)], egg))


def build_and_deploy_eggs(project, endpoint, apikey):
    egg_dirs = (f for f in glob('*') if isdir(f))

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
    log("Building egg in: %s" % os.getcwd())
    try:
        run('python setup.py bdist_egg')
    except CalledProcessError:
        # maybe a C extension or distutils package, forcing bdist_egg
        log("Couldn't build an egg with vanilla setup.py, trying with setuptools...")
        run('python -c  "import setuptools; __file__=\'setup.py\'; execfile(\'setup.py\')" bdist_egg')

    _deploy_dependency_egg(project, endpoint, apikey)


def _deploy_dependency_egg(project, endpoint, apikey):
    name = _get_dependency_name()
    version = _get_dependency_version(name)
    egg_name, egg_path = _get_egg_info(name)

    # XXX: Should endpoint point to /api/ instead of /api/scrapyd/ by default?
    url = urljoin(endpoint, '../eggs/add.json')
    data = {'project': project, 'name': name, 'version': version}
    files = {'egg': (egg_name, open(egg_path, 'rb'))}
    auth = (apikey, '')

    log('Deploying dependency to Scrapy Cloud project "%s"' % project)
    make_deploy_request(url, data, files, auth)
    success = "Deployed eggs list at: https://dash.scrapinghub.com/p/%s/eggs"
    log(success % project)


def _last_line_of(s):
    return s.split('\n')[-1]


def _get_dependency_name():
    # In some cases, python setup.py --name returns more than one line, so we use the last one to get the name
    return _last_line_of(run('python setup.py --name'))


def _get_dependency_version(name):
    if isdir('.git'):
        return pwd_git_version()
    elif isdir('.hg'):
        return pwd_hg_version()
    elif isdir('.bzr'):
        return pwd_bzr_version()

    version = _last_line_of(run('python setup.py --version'))
    return "%s-%s" % (name, version)


def _get_egg_info(name):
    egg_filename = name.replace('-', '_')
    egg_path_glob = os.path.join('dist', '%s*' % egg_filename)
    egg_path = glob(egg_path_glob)[0]
    return (egg_filename, egg_path)


def validate_jobid(jobid):
    if not bool(re.match(r'\d+/\d+/\d+$', jobid)):
        err = 'Job ID {} is invalid. Format should be\
               projectid/spiderid/jobid'.format(jobid)
        raise ClickException(err)


def get_job(jobid):
    # XXX: Lazy import to avoid circular dependency. Needs refactoring
    from shub.config import get_target
    validate_jobid(jobid)
    project, endpoint, apikey = get_target(jobid.split('/')[0])
    hsc = HubstorageClient(auth=apikey)
    job = hsc.get_job(jobid)
    if not job.metadata:
        raise ClickException('Job {} does not exist'.format(jobid))
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
