import glob
import os
import shutil
import tempfile

import click

from shub.exceptions import NotFoundException, ShubException, SubcommandException
from shub.utils import (create_default_setup_py, inside_project, remember_cwd,
                        run_cmd, run_python)

HELP = """
Build the egg of the current folder's Scrapy project and write it to FILENAME,
without deploying it:

    shub build-egg myproject.egg

This is the egg that `shub deploy` builds and uploads to Scrapy Cloud. To
deploy an egg you built this way, run:

    shub deploy --egg myproject.egg

Note that this command is about your project's own egg, not about its
dependencies. To make third-party libraries available to your project on
Scrapy Cloud, list them in the `requirements` section of your scrapinghub.yml
instead.

If the project is inside a git repository, the egg is built from a copy of
the working directory that leaves out anything git considers ignored (e.g.
via .gitignore), so build artifacts, local secrets, and stray virtualenvs
don't end up in the egg. Uncommitted changes to tracked files are still
included.
"""

SHORT_HELP = "Build the project egg without deploying it"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("filename", type=click.Path(dir_okay=False, writable=True, readable=False))
@click.option("-d", "--debug", help="Debug mode (do not remove build dir)",
              is_flag=True)
def cli(filename, debug):
    build_egg_cmd(filename, debug)


def build_egg_cmd(filename, debug=False):
    tmpdir = None
    try:
        egg, tmpdir = build_project_egg()
        click.echo("Writing egg to %s" % filename)
        try:
            shutil.copyfile(egg, filename)
        except OSError as e:
            raise ShubException(
                "Could not write egg to %s: %s" % (filename, e.strerror or e))
    finally:
        remove_build_dir(tmpdir, debug)


def build_project_egg():
    """
    Build the egg of the Scrapy project that contains the current directory.

    Return the path to the egg and the temporary directory it was built in.
    Callers are expected to clean up that directory afterwards, see
    ``remove_build_dir()``.
    """
    if not inside_project():
        raise NotFoundException("No Scrapy project found in this location.")
    git = shutil.which('git')
    if git:
        try:
            return _build_egg_from_git_filtered_files(git)
        except SubcommandException:
            # Not a git repository (or `git ls-files` otherwise failed): fall
            # back to building from the working directory as-is.
            pass
    return _build_egg_in_cwd()


def remove_build_dir(tmpdir, debug=False):
    """
    Remove the temporary directory returned by ``build_project_egg()``, unless
    ``debug`` is set: then keep it for inspection and tell the user where it
    is. Do nothing if there is no such directory, e.g. because an existing egg
    is used instead of building one.
    """
    if not tmpdir:
        return
    if debug:
        click.echo("Output dir not removed: %s" % tmpdir)
    else:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _build_egg_in_cwd():
    create_default_setup_py()
    d = tempfile.mkdtemp(prefix="shub-deploy-")
    run_python(['setup.py', 'clean', '-a', 'bdist_egg', '-d', d])
    egg = glob.glob(os.path.join(d, '*.egg'))[0]
    return egg, d


def _build_egg_from_git_filtered_files(git):
    """
    Copy the working directory into a temporary directory, leaving out
    anything git considers ignored (via `git ls-files`), then build the egg
    from there.

    Tracked files are copied with their current, possibly uncommitted,
    contents, and untracked-but-not-ignored files are included too: this only
    strips out gitignored cruft (build artifacts, local secrets, stray
    virtualenvs, etc.), it doesn't require anything to be committed.
    """
    paths = run_cmd(
        [git, 'ls-files', '--cached', '--others', '--exclude-standard'],
    ).splitlines()
    filtered_dir = tempfile.mkdtemp(prefix="shub-deploy-filtered-")
    try:
        for path in paths:
            if not os.path.isfile(path):
                # e.g. a tracked file staged for deletion but not yet removed
                # from the index
                continue
            dest = os.path.join(filtered_dir, path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(path, dest)
        with remember_cwd():
            os.chdir(filtered_dir)
            return _build_egg_in_cwd()
    finally:
        shutil.rmtree(filtered_dir, ignore_errors=True)
