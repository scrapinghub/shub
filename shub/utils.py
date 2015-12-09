from __future__ import unicode_literals, absolute_import
import importlib
import os
import subprocess
import sys
import re

from glob import glob
from os.path import isdir
from subprocess import Popen, PIPE, CalledProcessError

import requests

from click import ClickException
from hubstorage import HubstorageClient

from shub.auth import find_api_key
from shub.click_utils import log
from shub.exceptions import AuthException

SCRAPY_CFG_FILE = os.path.expanduser("~/.scrapy.cfg")
FALLBACK_ENCODING = 'utf-8'
STDOUT_ENCODING = sys.stdout.encoding or FALLBACK_ENCODING


def missing_modules(*modules):
    """Receives a list of module names and returns those which are missing"""
    missing = []
    for module_name in modules:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(module_name)
    return missing


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


def get_cmd_output(cmd):
    return Popen(cmd, stdout=PIPE).communicate()[0].decode(STDOUT_ENCODING)


def pwd_git_version():
    process = Popen(['git', 'describe', '--always'], stdout=PIPE)
    commit_id = process.communicate()[0].decode(STDOUT_ENCODING).strip('\n')
    if process.wait() != 0:
        commit_id = get_cmd_output(['git', 'rev-list', '--count', 'HEAD']).strip('\n')

    branch = get_cmd_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip('\n')
    return '%s-%s' % (commit_id, branch)


def pwd_hg_version():
    commit_id = 'r%s' % get_cmd_output(['hg', 'tip', '--template', '{rev}'])

    branch = get_cmd_output(['hg', 'branch']).strip('\n')
    return '%s-%s' % (commit_id, branch)


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

def _is_egg_dir(f):
    if not isdir(f):
        return False

    files = os.listdir(f)

    # these folders are usually created by PIP when the egg is
    # checked out from a VCS.
    # check ssues #21 and #44 for more details
    pip_tmp_dir = 'pip-delete-this-directory.txt' in files

    return 'setup.py' in files and not pip_tmp_dir
def build_and_deploy_eggs(project_id, apikey):
    egg_dirs = (f for f in glob('*') if _is_egg_dir(f))

    for egg_dir in egg_dirs:
        os.chdir(egg_dir)
        build_and_deploy_egg(project_id, apikey)
        os.chdir('..')


def _build_decompressor_by_ext_map():
    unzip = 'unzip -q'

    return {'zip': unzip,
            'whl': unzip,
            'bz2': 'tar jxf',
            'gz': 'tar zxf'}


def _ext(file_path):
    return os.path.splitext(file_path)[1].strip('.')


def build_and_deploy_egg(project_id, apikey):
    """Builds and deploys the current dir's egg"""
    log("Building egg in: %s" % os.getcwd())
    try:
        run('python setup.py bdist_egg')
    except CalledProcessError:
        # maybe a C extension or distutils package, forcing bdist_egg
        log("Couldn't build an egg with vanilla setup.py, trying with setuptools...")
        run('python -c  "import setuptools; __file__=\'setup.py\'; execfile(\'setup.py\')" bdist_egg')

    _deploy_dependency_egg(apikey, project_id)


def _deploy_dependency_egg(apikey, project_id):
    name = _get_dependency_name()
    version = _get_dependency_version(name)
    egg_name, egg_path = _get_egg_info(name)

    url = 'https://dash.scrapinghub.com/api/eggs/add.json'
    data = {'project': project_id, 'name': name, 'version': version}
    files = {'egg': (egg_name, open(egg_path, 'rb'))}
    auth = (apikey, '')

    log('Deploying dependency to Scrapy Cloud project "%s"' % project_id)
    make_deploy_request(url, data, files, auth)
    success = "Deployed eggs list at: https://dash.scrapinghub.com/p/%s/eggs"
    log(success % project_id)


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
    validate_jobid(jobid)
    apikey = find_api_key()
    hsc = HubstorageClient(auth=apikey)
    job = hsc.get_job(jobid)
    if not job.metadata:
        raise ClickException('Job {} does not exist'.format(jobid))
    return job
