from __future__ import absolute_import

import os
import zipfile

import errno

from shub.compat import to_unicode
from six.moves.urllib.parse import urljoin

from io import BytesIO

import click
import requests

from shub.config import get_target_conf, ShubConfig

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
@click.argument("target", required=False, default='default')
def cli(target):
    main(target)


def main(target):
    targetconf = get_target_conf(target)

    url = urljoin(targetconf.endpoint, 'migrate-eggs.zip')
    params = {'project': targetconf.project_id}
    auth = (targetconf.apikey, '')

    response = requests.get(url, auth=auth, params=params, stream=True)

    with zipfile.ZipFile(BytesIO(response.content), 'r') as mfile:
        Migrator(mfile).start()


class Migrator(object):
    def __init__(self, mfile):
        self.mfile = mfile
        self.sh_yml = './scrapinghub.yml'
        self.conf = ShubConfig()
        self.conf.load_file(self.sh_yml)

        self.req_content = to_unicode(self.mfile.read('requirements.txt'))
        self.eggs = []

        for filename in self.mfile.namelist():
            if filename.endswith('.egg'):
                self.eggs.append(filename)

    def start(self):
        if self.eggs:
            self.migrate_eggs()

        self.migrate_requirements_txt()

        self.conf.save(self.sh_yml)

    def migrate_eggs(self):
        eggsdir = './eggs'
        msg = "Eggs will be stored in {}, are you sure ? ".format(eggsdir)
        click.confirm(msg)
        try:
            os.mkdir(eggsdir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        for filename in self.eggs:
            filepath = os.path.join(eggsdir, filename)
            if filepath in self.conf.eggs:
                continue

            self.conf.eggs.append(filepath)
            self.mfile.extract(filename, eggsdir)

    def migrate_requirements_txt(self):
        req_file = self.conf.requirements_file or './requirements.txt'

        if os.path.isfile(req_file):
            y = click.confirm(
                'requirements.txt already exists, '
                'are you sure to override it ?'
            )
            if not y:
                click.echo('Aborting')
                return

        self.conf.requirements_file = req_file

        with open(self.conf.requirements_file, 'w') as reqfile:
            reqfile.write(self.req_content)
