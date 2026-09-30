import os
import shutil
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import click
import requests
import yaml
from click.formatting import HelpFormatter

from shub.exceptions import (
    BadParameterException,
    NotFoundException,
    RemoteErrorException,
)

EXAMPLE_REPO = "scrapinghub/custom-images-examples"
AVAILABLE_PROJECTS_URL = (
    f"https://raw.githubusercontent.com/{EXAMPLE_REPO}/master/bootstrap_projects.yml"
)

HELP = """
Through custom images, Scrapinghub allows you to run crawlers written in any
language you want. To get you started, we prepared a few examples projects in
different programming languages and frameworks. You can find them in our custom
images repository at:

    https://github.com/scrapinghub/custom-images-examples

The 'shub bootstrap' command clones an example project to the current directory
so that you can start hacking right away.

Run

    shub bootstrap -l

to get a list of all available example projects, then run

    shub bootstrap PROJECTNAME

to clone it.
"""

SHORT_HELP = "Clone custom image example project"


def list_projects_callback(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    projects = get_available_projects()
    list_projects(projects)
    ctx.exit()


@click.command(help=HELP, short_help=SHORT_HELP)
@click.option(
    "-l",
    "--list",
    "list_projects",
    help="list available projects",
    is_flag=True,
    callback=list_projects_callback,
    expose_value=False,
    is_eager=True,
)
@click.argument("project")
@click.argument("target_dir", required=False)
def cli(project, target_dir):
    target_dir = os.path.normpath(Path.cwd() / (target_dir or project))
    if Path(target_dir).exists():
        raise BadParameterException(
            f"Target directory {target_dir} already exists, please delete it or supply a "
            "non-existing target."
        )
    projects = get_available_projects()
    if project not in projects:
        raise NotFoundException(
            f"There is no example project named '{project}'. Run 'shub bootstrap -l' "
            "to get a list of all available projects."
        )
    click.echo("Downloading custom image examples")
    repo_zip = get_repo_zip(EXAMPLE_REPO)
    click.echo(f"Cloning project '{project}' into {target_dir}")
    unzip_project(repo_zip, project=projects[project], target_dir=target_dir)


def get_available_projects():
    try:
        resp = requests.get(AVAILABLE_PROJECTS_URL)  # noqa: S113
        resp.raise_for_status()
    except (requests.HTTPError, requests.ConnectionError) as e:
        raise RemoteErrorException(
            "There was an error while getting the list of available projects "
            "from GitHub: {}.\n\nPlease check your connection or go to\n  {}\n"
            "to browse the custom image examples manually."
            "".format(e, f"https://github.com/{EXAMPLE_REPO}")
        ) from e
    return yaml.safe_load(resp.text)


def list_projects(projects):
    formatter = HelpFormatter()
    with formatter.section("Available projects"):
        formatter.write_dl(
            sorted(
                [(name, info["description"]) for name, info in projects.items()],
                key=lambda x: x[0],
            )
        )
    click.echo(formatter.getvalue().strip())


def get_repo_zip(repo):
    zip_url = f"https://github.com/{repo}/archive/master.zip"
    resp = requests.get(zip_url)  # noqa: S113
    return zipfile.ZipFile(BytesIO(resp.content))


def unzip_project(repo_zip, project, target_dir):
    filenames = repo_zip.namelist()
    repo_dirname = filenames[0]
    project_filenames = [
        fn for fn in filenames if fn.startswith(repo_dirname + project["path"])
    ]
    tempdir = tempfile.mkdtemp()
    repo_zip.extractall(path=tempdir, members=project_filenames)
    shutil.move(
        Path(tempdir, repo_dirname, project["path"]),
        target_dir,
    )
    shutil.rmtree(tempdir)
