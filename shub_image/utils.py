import os
import re
import click
import importlib
import contextlib

from six import string_types
import ruamel.yaml as yaml

from shub import config as shub_config
from shub import utils as shub_utils
from shub import exceptions as shub_exceptions


DEFAULT_DOCKER_VERSION = '1.17'
STATUS_FILE_LOCATION = '.releases'
_VALIDSPIDERNAME = re.compile('^[a-z0-9][-._a-z0-9]+$', re.I)


def debug_log(msg):
    ctx = click.get_current_context(True)
    if ctx and ctx.params.get('debug'):
        click.echo(msg)


@contextlib.contextmanager
def remember_cwd():
    current_dir = os.getcwd()
    try:
        yield
    finally:
        os.chdir(current_dir)


class ReleaseConfig(shub_config.ShubConfig):

    def __init__(self, *args, **kwargs):
        super(ReleaseConfig, self).__init__(*args, **kwargs)
        self.images = {}

    def load(self, stream):
        """ Modified load logic to read images as well """
        super(ReleaseConfig, self).load(stream)
        try:
            # we have to read the stream twice to avoid
            # copy-pasting all the logic from shub tool
            stream.seek(0)
            yaml_cfg = yaml.safe_load(stream)
            if not yaml_cfg:
                return
            getattr(self, 'images').update(yaml_cfg.get('images', {}))
        except (yaml.YAMLError, AttributeError):
            # AttributeError: stream is valid YAML but not dictionary-like
            raise shub_exceptions.ConfigParseException

    def get_image(self, target):
        """Return image for given target."""
        try:
            return self.images[target]
        except KeyError:
            raise shub_exceptions.NotFoundException(
                "Could not find image for %s. Please define"
                " it in your scrapinghub.yml." % target)


def load_release_config():
    """ shub.config.load_shub_config with replaced config class """
    shub_config.ShubConfig = ReleaseConfig
    return shub_config.load_shub_config()


def missing_modules(*modules):
    """Receives a list of module names and returns those which are missing"""
    missing = []
    for module_name in modules:
        try:
            importlib.import_module(module_name)
        except ImportError:
            if module_name == 'docker':
                missing.append('docker-py')
            else:
                missing.append(module_name)
    return missing


def get_project_dir():
    """ A helper to get project root dir.
        Used by init/build command to locate Dockerfile.
    """
    if not shub_utils.inside_project():
        raise shub_exceptions.BadConfigException("Not inside a project")
    return os.path.dirname(shub_utils.closest_file('scrapy.cfg'))


def get_docker_client():
    """A helper to initiate Docker client"""
    try:
        import docker
    except ImportError:
        raise ImportError('You need docker-py installed for the cmd')

    class CustomDockerClient(docker.Client):

        # XXX: workaround for https://github.com/docker/docker-py/issues/1059
        def _stream_helper(self, response, decode=False):
            it = super(CustomDockerClient, self)._stream_helper(response, decode=decode)
            for data in it:
                if not isinstance(data, string_types):
                    yield data
                for line in data.split('\r\n'):
                    line = line.strip()
                    if line:
                        yield line

    docker_host = os.environ.get('DOCKER_HOST')
    tls_config = None
    if os.environ.get('DOCKER_TLS_VERIFY', False):
        tls_cert_path = os.environ.get('DOCKER_CERT_PATH')
        if not tls_cert_path:
            tls_cert_path = os.path.join(os.path.expanduser('~'), '.docker')
        apply_path_fun = lambda name: os.path.join(tls_cert_path, name)
        tls_config = docker.tls.TLSConfig(
            client_cert=(apply_path_fun('cert.pem'),
                         apply_path_fun('key.pem')),
            verify=apply_path_fun('ca.pem'),
            assert_hostname=False)
        docker_host = docker_host.replace('tcp://', 'https://')
    version = os.environ.get('DOCKER_VERSION', DEFAULT_DOCKER_VERSION)
    return CustomDockerClient(
        base_url=docker_host,
        version=version,
        tls=tls_config)


def format_image_name(image_name, image_tag):
    """Format image name using image tag"""
    parts = image_name.rsplit('/', 1)
    # check if tag is already here
    if ':' in parts[-1]:
        # change name to shorter version w/o existing tag
        click.echo('Please use --version param to specify tag')
        image_name = image_name.rsplit(':', 1)[0]
    if not image_tag:
        config = shub_config.load_shub_config()
        image_tag = config.get_version()
    return '{}:{}'.format(image_name, image_tag)


def get_credentials(username=None, password=None, insecure=False,
                    apikey=None, target_apikey=None):
    """ A helper function to get credentials based on cmdline options.

    Returns a tuple with 2 strings: (username, password).

    When working with registries where only username matters:
    missing password leads to auth request to registry authentication service
    without 'account' query parameter which breaks login.
    """
    if insecure:
        return None, None
    elif apikey:
        return apikey, ' '
    elif username:
        if password is None:
            raise click.BadParameter(
                'Password is required when passing username.')
        return username, password
    elif password:
        raise click.BadParameter(
            'Username is required when passing password.')
    return target_apikey, ' '


def store_status_url(status_url, limit):
    """Load status file and update it with a url"""
    data = _load_status_file(STATUS_FILE_LOCATION)
    if not data:
        data[0] = status_url
        _update_status_file(data, STATUS_FILE_LOCATION)
        return 0
    for stored_id, stored_url in data.items():
        if stored_url == status_url:
            click.echo("Found same status_url: {}".format(stored_id))
            return stored_id
    status_id = max(data.keys()) + 1
    data[status_id] = status_url
    if len(data) > limit:
        data.popitem()
    _update_status_file(data, STATUS_FILE_LOCATION)
    return status_id


def load_status_url(status_id):
    """ Load status url from file by status_id"""
    if not os.path.isfile(STATUS_FILE_LOCATION):
        raise shub_exceptions.NotFoundException(
            'Status file is not found at {}'.format(STATUS_FILE_LOCATION))
    data = _load_status_file(STATUS_FILE_LOCATION)
    # return latest status url if status id is not provided
    if not isinstance(status_id, int) and data:
        max_status_id = max(data.keys())
        click.echo('Getting results for latest status id {}.'
                   .format(max_status_id))
        return data[max_status_id]
    if status_id not in data:
        raise shub_exceptions.NotFoundException(
            "Status url with id {} is not found".format(status_id))
    return data[status_id]


def _load_status_file(path):
    """ Open status file and parse it """
    data = {}
    if not os.path.isfile(path):
        return data
    with open(path, 'r') as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError, exc:
            raise shub_exceptions.BadConfigException(
                "Error reading releases file:\n{}".format(exc))
    if not isinstance(data, dict):
        raise shub_exceptions.BadConfigException(
            "Releases file has wrong format ({}).".format(data))
    return data


def _update_status_file(data, path):
    """ Save status file with updated data """
    with open(path, 'w') as status_file:
        yaml.dump(data, status_file, default_flow_style=False)


def valid_spiders(buf):
    """Filter out garbage and only let valid spider names in
    >>> _valid_spiders('Update rootfs\\nsony.com\\n\\nsoa-uk\\n182-blink.com')
    ['182-blink.com', 'soa-uk', 'sony.com']
    >>> _valid_spiders('-spiders\\nA77aque')
    ['A77aque']
    """
    return sorted(filter(_VALIDSPIDERNAME.match, buf.splitlines()))
