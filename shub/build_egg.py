import io
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

import click

from shub.exceptions import NotFoundException, ShubException, SubcommandException
from shub.utils import (
    create_default_setup_py,
    inside_project,
    remember_cwd,
    run_cmd,
    run_python,
)

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
included. To build the egg only from what is committed, use:

    shub build-egg --from-head myproject.egg
"""

SHORT_HELP = "Build the project egg without deploying it"


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument(
    "filename", type=click.Path(dir_okay=False, writable=True, readable=False)
)
@click.option(
    "-d", "--debug", help="Debug mode (do not remove build dir)", is_flag=True
)
@click.option(
    "--from-head",
    is_flag=True,
    help="Build the egg from the files committed to git HEAD",
)
def cli(filename, debug, from_head):
    build_egg_cmd(filename, debug, from_head)


def build_egg_cmd(filename, debug=False, from_head=False):
    tmpdir = None
    try:
        egg, tmpdir = build_project_egg(from_head)
        click.echo(f"Writing egg to {filename}")
        try:
            shutil.copyfile(egg, filename)
        except OSError as e:
            raise ShubException(
                f"Could not write egg to {filename}: {e.strerror or e}"
            ) from e
    finally:
        remove_build_dir(tmpdir, debug)


def build_project_egg(from_head=False):
    """
    Build the egg of the Scrapy project that contains the current directory,
    from the files committed to git HEAD if *from_head* is true.

    Return the path to the egg and the temporary directory it was built in.
    Callers are expected to clean up that directory afterwards, see
    ``remove_build_dir()``.
    """
    if not inside_project():
        raise NotFoundException("No Scrapy project found in this location.")
    git = shutil.which("git")
    if from_head:
        if not git:
            raise NotFoundException("--from-head requires git.")
        return _build_egg_from_git_head(git)
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
        click.echo(f"Output dir not removed: {tmpdir}")
    else:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _build_egg_in_cwd():
    create_default_setup_py()
    d = tempfile.mkdtemp(prefix="shub-deploy-")
    run_python(["setup.py", "clean", "-a", "bdist_egg", "-d", d])
    egg = str(next(Path(d).glob("*.egg")))
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
        [git, "ls-files", "--cached", "--others", "--exclude-standard"],
    ).splitlines()
    filtered_dir = tempfile.mkdtemp(prefix="shub-deploy-filtered-")
    try:
        for path in paths:
            if not Path(path).is_file():
                # e.g. a tracked file staged for deletion but not yet removed
                # from the index
                continue
            dest = Path(filtered_dir, path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        with remember_cwd():
            os.chdir(filtered_dir)
            return _build_egg_in_cwd()
    finally:
        shutil.rmtree(filtered_dir, ignore_errors=True)


def _build_egg_from_git_head(git):
    """Build the egg from the files under the current directory as committed
    to git HEAD."""
    try:
        archive = subprocess.run(  # noqa: S603
            [git, "archive", "HEAD"],
            capture_output=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        raise SubcommandException(
            "Error while calling 'git archive HEAD':\n\n"
            + e.stderr.decode(errors="replace")
        ) from e
    head_dir = tempfile.mkdtemp(prefix="shub-deploy-head-")
    try:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extraction_filter = getattr(tarfile, "data_filter", None)
            tar.extractall(head_dir)  # noqa: S202
        with remember_cwd():
            os.chdir(head_dir)
            return _build_egg_in_cwd()
    finally:
        shutil.rmtree(head_dir, ignore_errors=True)
