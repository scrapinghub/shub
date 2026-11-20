import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import click
import requests

from shub.compat import to_unicode
from shub.config import ShubConfig, get_target_conf
from shub.exceptions import ShubException
from shub.utils import check_not_symlink

HELP = """
Migrate eggs stored in Dash's "Code & Deploy" section.

Eggs that are available in PYPI will be stored in requirements.txt file.
The rest will be stored in user provided directory and send to Dash
for each deployment.

After the operation is completed, please review changes made to
scrapinghub.yml and requirements.txt files.
"""

SHORT_HELP = "Migrate dash eggs to requirements.txt and project's directory"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
def cli(target):
    main(target)


def main(target):
    targetconf = get_target_conf(target)

    url = urljoin(targetconf.endpoint, "migrate-eggs.zip")
    params = {"project": targetconf.project_id}
    auth = (targetconf.apikey, "")

    response = requests.get(url, auth=auth, params=params, stream=True)  # noqa: S113

    with zipfile.ZipFile(BytesIO(response.content), "r") as mfile:
        Migrator(mfile).start()


def _check_inside_project(path):
    """Refuse to write to a symbolic link or to a path outside of the project
    directory, which is the current directory."""
    check_not_symlink(path)
    if not Path(path).resolve().is_relative_to(Path.cwd().resolve()):
        raise ShubException(
            f"Refusing to write to {path}: it is outside of the project directory."
        )


class Migrator:
    def __init__(self, mfile):
        self.mfile = mfile
        self.sh_yml = "./scrapinghub.yml"
        self.conf = ShubConfig()
        self.conf.load_file(self.sh_yml)

        self.req_content = to_unicode(self.mfile.read("requirements.txt"))
        self.eggs = []

        for filename in self.mfile.namelist():
            if filename.endswith(".egg"):
                self.eggs.append(filename)

    def start(self):
        _check_inside_project(self.sh_yml)
        if self.eggs:
            self.migrate_eggs()

        self.migrate_requirements_txt()

        self.conf.save(self.sh_yml)

    def migrate_eggs(self):
        eggsdir = "./eggs"
        _check_inside_project(eggsdir)
        msg = f"Eggs will be stored in {eggsdir}, are you sure ? "
        click.confirm(msg, abort=True)
        Path(eggsdir).mkdir(exist_ok=True)

        for filename in self.eggs:
            filepath = f"{eggsdir}/{filename}"
            if filepath in self.conf.eggs:
                continue

            _check_inside_project(filepath)
            self.conf.eggs.append(filepath)
            self.mfile.extract(filename, eggsdir)

    def migrate_requirements_txt(self):
        req_file = self.conf.requirements_file or "./requirements.txt"
        _check_inside_project(req_file)

        if Path(req_file).is_file():
            y = click.confirm(
                "requirements.txt already exists, are you sure to override it ?"
            )
            if not y:
                click.echo("Aborting")
                return

        self.conf.requirements_file = req_file

        with Path(self.conf.requirements_file).open("w") as reqfile:
            reqfile.write(self.req_content)
