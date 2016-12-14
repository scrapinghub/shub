import os
import textwrap
from string import Template

import click
from six.moves import input

from shub import exceptions as shub_exceptions
from shub import utils as shub_utils
from shub.image import utils


DOCKER_APP_DIR = '/app'
DOCKERFILE_TEMPLATE = """
FROM $base_image
$system_deps
$system_env
RUN mkdir -p {docker_app_dir}
WORKDIR {docker_app_dir}
$requirements
COPY . {docker_app_dir}
RUN python setup.py install
""".format(docker_app_dir=DOCKER_APP_DIR)

BASE_SYSTEM_DEPS = [
    'telnet', 'vim', 'htop', 'strace', 'ltrace', 'iputils-ping', 'lsof'
]
BASE_PYTHON_DEPS = [
    'BeautifulSoup==3.2.0', 'MySQL-python==1.2.3', 'Scrapy==1.0.3',
    'Twisted==11.1.0', 'boto==2.28.0', 'guppy==0.1.10', 'hubstorage==0.19.1',
    'ipython==3.2.1', 'lxml==3.4.4', 'numpy==1.6.1', 'pika==0.9.14',
    'psycopg2==2.4.5', 'pymongo==2.6.3', 'queuelib==1.2.2',
    'raven==5.0.0', 'requests==2.5.3', 'scrapely==0.12.0',
    'scrapinghub==1.7.0', 'scrapylib==1.6.0', 'setproctitle==1.0.1',
    'slybot==0.12.1', 'w3lib==1.13.0',
    'scrapinghub-entrypoint-scrapy==0.6.0'
]

SHORT_HELP = "Form Dockerfile for a given Scrapy project and save it."

HELP = """
Init command creates a Dockerfile for your project. It's likely that
default values will fit to you, otherwise you will be able to edit your
Dockerfile as you want.

System deps for Dockerfile:
By default there're several system deps to be included to the Dockerfile ({}),
you can extend it via --add-deps option, or redefine at all with --base-deps
option.

Python deps for Dockerfile:
The correct way to install python deps is using requirements.txt. If there's
no requirements.txt in the project_dir folder and no provided value for it
via --requirements option, we'll create new requirements.txt in the
project_dir with the recommended deps(use --list-recommended-reqs to list it).

You should also include scrapinghub-entrypoint-scrapy package to your py-reqs,
it's a necessary condition to run your project with Kumo (use shub-image test
to check if your image fits our expectations).
""".format(BASE_SYSTEM_DEPS)


def list_recommended_python_reqs(ctx, param, value):
    """List recommended Python requirements"""
    if not value:
        return
    click.echo("Recommended Python deps list:")
    for dep in BASE_PYTHON_DEPS:
        click.echo('- {}'.format(dep))
    ctx.exit()


@click.command(help=HELP, short_help=SHORT_HELP)
@click.option("--list-recommended-reqs", is_flag=True, is_eager=True,
              expose_value=False, callback=list_recommended_python_reqs,
              help="list recommended python requirements")
@click.option("--project", default="default",
              help="project name to get settings module from scrapy.cfg")
@click.option("--base-image", default="python:2.7",
              help="base docker image name")
@click.option("--base-deps", default=','.join(BASE_SYSTEM_DEPS),
              help="a comma-separated list with base system deps")
@click.option("--add-deps",
              help="a comma-separated list with additional system deps")
@click.option("--requirements", default="requirements.txt",
              help="path to requirements.txt")
def cli(project, base_image, base_deps, add_deps, requirements):
    project_dir = utils.get_project_dir()
    scrapy_config = shub_utils.get_config()
    if not scrapy_config.has_option('settings', project):
        raise shub_exceptions.BadConfigException(
            'Settings for the project is not found')
    settings_module = scrapy_config.get('settings', project)
    values = {
        'base_image':   base_image,
        'system_deps':  _format_system_deps(base_deps, add_deps),
        'system_env':   _format_system_env(settings_module),
        'requirements': _format_requirements(project_dir, requirements),
    }
    values = {key: value if value else '' for key, value in values.items()}
    source = Template(DOCKERFILE_TEMPLATE.strip())
    results = source.substitute(values)
    results = results.replace('\n\n', '\n')

    click.echo("The following Dockerfile will be created:\n{}".format(results))
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    while True:
        dockefile_path = os.path.join(project_dir, 'Dockerfile')
        choice = input("Save to {}: (y/n)".format(dockefile_path)).lower()
        if choice in valid:
            if valid[choice]:
                with open(dockefile_path, 'w') as dockerfile:
                    dockerfile.write(results)
                click.echo('Saved.')
            break
        click.echo("Please respond with 'yes'('y') or 'no'(n)")


def _format_system_deps(base_deps, add_deps):
    """Prepare a list with system dependencies install cmds"""
    system_deps = base_deps.split(',') if base_deps != '-' else []
    if add_deps:
        system_add_deps = add_deps.split(',')
        system_deps = list(set(system_deps + system_add_deps))
    if not system_deps:
        return
    deps_string = ' '.join(sorted(system_deps))
    commands = ["apt-get update -qq",
                "apt-get install -qy {}".format(deps_string),
                "rm -rf /var/lib/apt/lists/*"]
    return 'RUN ' + ' && \\\n    '.join(
        [_wrap(cmd) for cmd in commands])


def _wrap(text):
    """Wrap dependencies with separator"""
    lines = textwrap.wrap(text, subsequent_indent='    ',
                          break_long_words=False,
                          break_on_hyphens=False)
    return ' \\\n'.join(lines)


def _format_system_env(settings_module):
    rows = ['ENV TERM xterm']
    if settings_module:
        rows.append('ENV SCRAPY_SETTINGS_MODULE %s' % settings_module)
    return '\n'.join(rows)


def _format_requirements(project_dir, requirements):
    """Prepare cmds for project requirements"""
    rel_reqs_path = os.path.relpath(
        os.path.join(project_dir, requirements), project_dir)
    if os.path.isfile(rel_reqs_path):
        if rel_reqs_path.startswith('../'):
            raise shub_exceptions.BadParameterException(
                "requirements file must be inside your project directory"
                "(it's a demand of docker itself)")
    else:
        # let's create requirements.txt with base dependencies
        with open(rel_reqs_path, 'w') as reqs_file:
            reqs_file.writelines("%s\n" % l for l in BASE_PYTHON_DEPS)
        click.echo('Created base requirements.txt in project dir.')
    rows = [
        'COPY ./{} {}/requirements.txt'.format(rel_reqs_path, DOCKER_APP_DIR),
        'RUN pip install --no-cache-dir -r requirements.txt',
    ]
    return '\n'.join(rows)
