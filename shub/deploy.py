import sys, os, glob, tempfile, shutil, time, urllib2, netrc, json, click
from urlparse import urlparse, urljoin
from subprocess import Popen, PIPE, check_call

from w3lib.form import encode_multipart
import setuptools # not used in code but needed in runtime, don't remove!

from scrapy.utils.project import inside_project
from scrapy.utils.http import basic_auth_header
from scrapy.utils.python import retry_on_eintr
from scrapy.utils.conf import get_config, closest_scrapy_cfg

_SETUP_PY_TEMPLATE = \
"""# Automatically created by: shub deploy

from setuptools import setup, find_packages

setup(
    name         = 'project',
    version      = '1.0',
    packages     = find_packages(),
    entry_points = {'scrapy': ['settings = %(settings)s']},
)
"""

@click.command(help="Deploy Scrapy project to Scrapy Cloud")
@click.argument("target", required=False, default="default")
@click.option("-p", "--project", help="the project ID to deploy to", type=click.INT)
@click.option("-v", "--version", help="the version to use for deploying")
@click.option("-l", "--list-targets", help="list available targets", is_flag=True)
@click.option("-d", "--debug", help="debug mode (do not remove build dir)", is_flag=True)
@click.option("--egg", help="deploy the given egg, instead of building one", is_flag=True)
@click.option("--build-egg", help="only build the egg, don't deploy it", is_flag=True)
def cli(target, project, version, list_targets, debug, egg, build_egg):
    exitcode = 0
    if not inside_project():
        _log("Error: no Scrapy project found in this location")
        sys.exit(1)

    if list_targets:
        for name, target in _get_targets().items():
            click.echo(name)
        return

    tmpdir = None

    if build_egg: # build egg only
        egg, tmpdir = _build_egg()
        _log("Writing egg to %s" % build_egg)
        shutil.copyfile(egg, build_egg)
    else: # buld egg and deploy
        target = _get_target(target)
        project = _get_project(target, project)
        version = _get_version(target, version)
        if egg:
            _log("Using egg: %s" % egg)
            egg = egg
        else:
            _log("Packing version %s" % version)
            egg, tmpdir = _build_egg()
        if _upload_egg(target, egg, project, version):
            click.echo("Run your spiders at: https://dash.scrapinghub.com/p/%s/" % project)
        else:
            exitcode = 1

    if tmpdir:
        if debug:
            _log("Output dir not removed: %s" % tmpdir)
        else:
            shutil.rmtree(tmpdir)

    sys.exit(exitcode)

def _log(message):
    click.echo(message)

def _fail(message, code=1):
    _log(message)
    sys.exit(code)

def _get_project(target, project):
    project = project or target.get('project')
    if not project:
        raise _fail("Error: Missing project id")
    return str(project)

def _get_option(section, option, default=None):
    cfg = get_config()
    return cfg.get(section, option) if cfg.has_option(section, option) \
        else default

def _get_targets():
    cfg = get_config()
    baset = dict(cfg.items('deploy')) if cfg.has_section('deploy') else {}
    baset.setdefault('url', 'http://dash.scrapinghub.com/api/scrapyd/')
    targets = {}
    targets['default'] = baset
    for x in cfg.sections():
        if x.startswith('deploy:'):
            t = baset.copy()
            t.update(cfg.items(x))
            targets[x[7:]] = t
    return targets

def _get_target(name):
    try:
        return _get_targets()[name]
    except KeyError:
        raise _fail("Unknown target: %s" % name)

def _url(target, action):
    return urljoin(target['url'], action)

def _get_version(target, version):
    version = version or target.get('version')
    if version == 'HG':
        p = Popen(['hg', 'tip', '--template', '{rev}'], stdout=PIPE)
        d = 'r%s' % p.communicate()[0]
        p = Popen(['hg', 'branch'], stdout=PIPE)
        b = p.communicate()[0].strip('\n')
        return '%s-%s' % (d, b)
    elif version == 'GIT':
        p = Popen(['git', 'describe'], stdout=PIPE)
        d = p.communicate()[0].strip('\n')
        if p.wait() != 0:
            p = Popen(['git', 'rev-list', '--count', 'HEAD'], stdout=PIPE)
            d = 'r%s' % p.communicate()[0].strip('\n')

        p = Popen(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], stdout=PIPE)
        b = p.communicate()[0].strip('\n')
        return '%s-%s' % (d, b)
    elif version:
        return version
    else:
        return str(int(time.time()))

def _upload_egg(target, eggpath, project, version):
    with open(eggpath, 'rb') as f:
        eggdata = f.read()
    data = {
        'project': project,
        'version': version,
        'egg': ('project.egg', eggdata),
    }
    body, boundary = encode_multipart(data)
    url = _url(target, 'addversion.json')
    headers = {
        'Content-Type': 'multipart/form-data; boundary=%s' % boundary,
        'Content-Length': str(len(body)),
    }
    req = urllib2.Request(url, body, headers)
    _add_auth_header(req, target)
    _log('Deploying to Scrapy Cloud project "%s"' % project)
    return _http_post(req)

def _add_auth_header(request, target):
    if 'username' in target:
        u, p = target.get('username'), target.get('password', '')
        request.add_header('Authorization', basic_auth_header(u, p))
    else: # try netrc
        try:
            host = urlparse(target['url']).hostname
            a = netrc.netrc().authenticators(host)
            request.add_header('Authorization', basic_auth_header(a[0], a[2]))
        except (netrc.NetrcParseError, IOError, TypeError):
            pass

def _http_post(request):
    try:
        f = urllib2.urlopen(request)
        _log("Server response (%s):" % f.code)
        print f.read()
        return True
    except urllib2.HTTPError, e:
        _log("Deploy failed (%s):" % e.code)
        resp = e.read()
        try:
            d = json.loads(resp)
        except ValueError:
            print resp
        else:
            if "status" in d and "message" in d:
                print "Status: %(status)s" % d
                print "Message:\n%(message)s" % d
            else:
                print json.dumps(d, indent=3)
    except urllib2.URLError, e:
        _log("Deploy failed: %s" % e)

def _build_egg():
    closest = closest_scrapy_cfg()
    os.chdir(os.path.dirname(closest))
    if not os.path.exists('setup.py'):
        settings = get_config().get('settings', 'default')
        _create_default_setup_py(settings=settings)
    d = tempfile.mkdtemp(prefix="shub-deploy-")
    o = open(os.path.join(d, "stdout"), "wb")
    e = open(os.path.join(d, "stderr"), "wb")
    retry_on_eintr(check_call, [sys.executable, 'setup.py', 'clean', '-a', 'bdist_egg', '-d', d], stdout=o, stderr=e)
    o.close()
    e.close()
    egg = glob.glob(os.path.join(d, '*.egg'))[0]
    return egg, d

def _create_default_setup_py(**kwargs):
    with open('setup.py', 'w') as f:
        f.write(_SETUP_PY_TEMPLATE % kwargs)
