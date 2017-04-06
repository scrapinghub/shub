import os
import textwrap
from string import Template

import click

from shub import exceptions as shub_exceptions
from shub import utils as shub_utils
from shub.image import utils


DOCKER_APP_DIR = '/app'
DOCKERFILE_TEMPLATE = """\
FROM $base_image
$system_deps
$system_env
RUN mkdir -p {docker_app_dir}
WORKDIR {docker_app_dir}
$requirements
COPY . {docker_app_dir}
RUN python setup.py install
""".format(docker_app_dir=DOCKER_APP_DIR)

DEFAULT_BASE_IMAGE = "scrapinghub/scrapinghub-stack-scrapy:1.3"
RECOMMENDED_PYTHON_DEPS = [
    'guppy==0.1.10',
]

SHORT_HELP = "Create Dockerfile for existing Scrapy project."

HELP = """
Init command creates a Dockerfile for existing Scrapy project. This tool is for users
who want to create a custom Docker image and don't have a Dockerfile yet. If generated
Dockerfile doesn't fit your project feel free to edit it.

Python packages

If there's a requirements.txt file in the project directory - it will be added to the
Dockerfile. Also it's possible to provide a path to requirements file via --requirements
option. Otherwise new requirements.txt file will be created in the project directory
with the recommended Python packages. Use --list-recommended-reqs to list them.

It's recommended to include scrapinghub-entrypoint-scrapy package - it is a
support layer that passes data from the job to Scrapinghub storage. Otherwise
you will need to send data to Scrapinghub storage using HTTP API.

System packages

You can extend list of system packages installed in the image via --add-deps option.
"""


def list_recommended_python_reqs(ctx, param, value):
    """List recommended Python requirements"""
    if not value:
        return
    click.echo("Recommended Python deps list:")
    for dep in RECOMMENDED_PYTHON_DEPS:
        click.echo('- {}'.format(dep))
    ctx.exit()


def _deprecate_base_deps_parameter(ctx, param, value):
    if value:
        click.echo("WARNING: --base-deps parameter is deprecated. "
                   "Please use --add-deps parameter instead.",
                   err=True)
    return value


@click.command(help=HELP, short_help=SHORT_HELP)
@click.option("--list-recommended-reqs", is_flag=True, is_eager=True,
              expose_value=False, callback=list_recommended_python_reqs,
              help="list recommended python requirements")
@click.option("--project", default="default",
              help="project name to get settings module from scrapy.cfg")
@click.option("--base-image", default=DEFAULT_BASE_IMAGE,
              help="base docker image name")
@click.option("--base-deps", default='',
              help="[DEPRECATED] a comma-separated list with base system dependencies",
              callback=_deprecate_base_deps_parameter)
@click.option("--add-deps",
              help="a comma-separated list with additional system dependencies")
@click.option("--requirements", default="requirements.txt",
              help="path to requirements.txt")
def cli(project, base_image, base_deps, add_deps, requirements):
    project_dir = utils.get_project_dir()
    scrapy_config = shub_utils.get_config()
    if not scrapy_config.has_option('settings', project):
        raise shub_exceptions.BadConfigException(
            'Cannot find Scrapy project settings. Please ensure that current directory '
            'contains scrapy.cfg with settings section, see example at '
            'https://doc.scrapy.org/en/latest/topics/commands.html#default-structure-of-scrapy-projects')  # NOQA
    dockefile_path = os.path.join(project_dir, 'Dockerfile')
    if os.path.exists(dockefile_path):
        raise shub_exceptions.ShubException('Found a Dockerfile in the project directory, aborting')
    settings_module = scrapy_config.get('settings', project)
    values = {
        'base_image':   base_image,
        'system_deps':  _format_system_deps(base_deps, add_deps),
        'system_env':   _format_system_env(settings_module),
        'requirements': _format_requirements(project_dir, requirements),
    }
    values = {key: value if value else '' for key, value in values.items()}
    source = Template(DOCKERFILE_TEMPLATE)
    results = source.substitute(values)
    results = results.replace('\n\n', '\n')
    with open(dockefile_path, 'w') as dockerfile:
        dockerfile.write(results)
    click.echo("Dockerfile is saved to {}".format(dockefile_path))


def _format_system_deps(base_deps, add_deps):
    """Prepare a list with system dependencies install cmds"""
    system_deps = base_deps.split(',') if base_deps != '-' else []
    if add_deps:
        system_add_deps = add_deps.split(',')
        system_deps = list(set(system_deps + system_add_deps))
    system_deps = sorted(filter(None, system_deps))
    if not system_deps:
        return
    commands = ["apt-get update -qq",
                "apt-get install -qy {}".format(' '.join(system_deps)),
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
            reqs_file.writelines("%s\n" % l for l in RECOMMENDED_PYTHON_DEPS)
        click.echo('Created base requirements.txt in project dir.')
    rows = [
        'COPY ./{} {}/requirements.txt'.format(rel_reqs_path, DOCKER_APP_DIR),
        'RUN pip install --no-cache-dir -r requirements.txt',
    ]
    return '\n'.join(rows)
