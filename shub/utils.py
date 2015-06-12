import imp
import os
import netrc
import subprocess

from glob import glob
from os.path import isdir
from subprocess import Popen, PIPE, CalledProcessError

import requests

from shub.click_utils import log

SCRAPY_CFG_FILE = os.path.expanduser("~/.scrapy.cfg")
OS_WIN = True if os.name == 'nt' else False
NETRC_FILE = os.path.expanduser('~/_netrc') if OS_WIN else os.path.expanduser('~/.netrc')


def missing_modules(*modules):
    """Receives a list of module names and returns those which are missing"""
    missing = []
    for module_name in modules:
        try:
            imp.find_module(module_name)
        except ImportError:
            missing.append(module_name)
    return missing


def find_api_key():
    """Finds and returns the Scrapy Cloud APIKEY"""
    key = os.getenv("SHUB_APIKEY")
    if not key:
        key = get_key_netrc()
    return key


def get_key_netrc():
    """Gets the key from the netrc file"""
    try:
        info = netrc.netrc(NETRC_FILE)
    except IOError:
        return
    try:
        key, account, password = info.authenticators("scrapinghub.com")
    except TypeError:
        return
    if key:
        return key


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
        log("Deploy failed ({}):".format(rsp.status_code))
        log(rsp.text)
        return False
    except requests.RequestException as exc:
        log("Deploy failed: {}".format(exc))
        return False


def pwd_git_version():
    p = Popen(['git', 'describe', '--always'], stdout=PIPE)
    d = p.communicate()[0].strip('\n')
    if p.wait() != 0:
        p = Popen(['git', 'rev-list', '--count', 'HEAD'], stdout=PIPE)
        d = 'r%s' % p.communicate()[0].strip('\n')

    p = Popen(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], stdout=PIPE)
    b = p.communicate()[0].strip('\n')
    return '%s-%s' % (d, b)


def pwd_hg_version():
    p = Popen(['hg', 'tip', '--template', '{rev}'], stdout=PIPE)
    d = 'r%s' % p.communicate()[0]
    p = Popen(['hg', 'branch'], stdout=PIPE)
    b = p.communicate()[0].strip('\n')
    return '%s-%s' % (d, b)


def pwd_bzr_version():
    p = Popen(['bzr', 'revno'], stdout=PIPE)
    d = '%s' % p.communicate()[0].strip()
    return d


def run(cmd):
    output = subprocess.check_output(cmd, shell=True)
    return output.strip()


def decompress_egg_files():
    decompressor_by_ext = _build_decompressor_by_ext_map()
    eggs = (f for ext in decompressor_by_ext for f in glob('*.%s' % ext))

    for egg in eggs:
        log("Uncompressing: %s" % egg)
        run("%s %s" % (decompressor_by_ext[_ext(egg)], egg))


def build_and_deploy_eggs(project_id):
    egg_dirs = (f for f in glob('*') if isdir(f))

    for egg_dir in egg_dirs:
        os.chdir(egg_dir)
        build_and_deploy_egg(project_id)
        os.chdir('..')


def _build_decompressor_by_ext_map():
    unzip = 'unzip -q'
    targz = 'tar zxf'

    return {'zip': unzip,
            'whl': unzip,
            'gz': targz}


def _ext(file_path):
    return os.path.splitext(file_path)[1].strip('.')


def build_and_deploy_egg(project_id):
    """Builds and deploys the current dir's egg"""
    log("Building egg in: %s" % os.getcwd())
    try:
        run('python setup.py bdist_egg')
    except CalledProcessError:
        # maybe a C extension or distutils package, forcing bdist_egg
        run('python -c  "import setuptools; execfile(\'setup.py\')" bdist_egg')

    _deploy_dependency_egg(find_api_key(), project_id)


def _deploy_dependency_egg(shub_apikey, project_id):
    name = _get_dependency_name()
    version = _get_dependency_version(name)
    egg_name, egg_path = _get_egg_info(name)

    url = 'https://dash.scrapinghub.com/api/eggs/add.json'
    data = {'project': project_id, 'name': name, 'version': version}
    files = {'egg': (egg_name, open(egg_path, 'rb'))}
    auth = (shub_apikey, '')

    log('Deploying dependency to Scrapy Cloud project "%s"' % project_id)
    make_deploy_request(url, data, files, auth)
    success = "Deployed eggs list at: https://dash.scrapinghub.com/p/%s/eggs"
    log(success % project_id)


def _get_dependency_name():
    return run('python setup.py --name')


def _get_dependency_version(name):
    if isdir('.git'):
        return pwd_git_version()
    elif isdir('.hg'):
        return pwd_hg_version()
    elif isdir('.bzr'):
        return pwd_bzr_version()

    return "%s-%s" % (name, run('python setup.py --version'))


def _get_egg_info(name):
    egg_filename = name.replace('-', '_')
    egg_path_glob = os.path.join('dist', '%s*' % egg_filename)
    egg_path = glob(egg_path_glob)[0]
    return (egg_filename, egg_path)
