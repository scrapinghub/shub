import glob
import shutil
from pathlib import Path
from urllib.parse import urljoin

import click
import toml

from shub.build_egg import build_egg_cmd, build_project_egg, remove_build_dir
from shub.config import SH_IMAGES_REGISTRY, list_targets_callback, load_shub_config
from shub.exceptions import (
    BadParameterException,
    NotFoundException,
    ShubDeprecationWarning,
    ShubException,
    SubcommandException,
    print_warning,
)
from shub.image.upload import upload_cmd
from shub.utils import (
    _project_cwd,
    create_scrapinghub_yml_wizard,
    make_deploy_request,
    run_cmd,
)

# The previous name of build_project_egg(), which deploy wrappers built on top
# of shub still import from here.
_build_egg = build_project_egg

HELP = """
Deploy the current folder's Scrapy project to Scrapy Cloud.

If you do not supply `target`, the default target from scrapinghub.yml will be
used. If you have no scrapinghub.yml, you will be guided through a short wizard
to create one. You can also specify a numerical project ID:

    shub deploy 12345

Or use any of the targets defined in your scrapinghub.yml:

    shub deploy production

To see a list of all defined targets, run:

    shub deploy -l

You can also deploy an existing project egg:

    shub deploy --egg egg_name

To build an egg without deploying it, use `shub build-egg`:

    shub build-egg egg_name

If the project is inside a git repository, the egg is built from a copy of
the working directory that leaves out anything git considers ignored (e.g.
via .gitignore), so build artifacts, local secrets, and stray virtualenvs
don't end up in the deploy. Uncommitted changes to tracked files are still
included.
"""

SHORT_HELP = "Deploy Scrapy project to Scrapy Cloud"


def _deprecate_build_egg_parameter(ctx, param, value):
    if value is not None:
        print_warning(
            "--build-egg parameter is deprecated. "
            "Please use `shub build-egg FILENAME` instead.",
            ShubDeprecationWarning,
        )
    return value


@click.command(help=HELP, short_help=SHORT_HELP)
@click.argument("target", required=False, default="default")
@click.option(
    "-l",
    "--list-targets",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=list_targets_callback,
    help="List available project names defined in your config",
)
@click.option("-V", "--version", help="The version to use for deploying")
@click.option(
    "-d", "--debug", help="Debug mode (do not remove build dir)", is_flag=True
)
@click.option("--egg", help="Deploy the given egg, instead of building one")
@click.option(
    "--build-egg",
    type=click.Path(dir_okay=False, writable=True, readable=False),
    callback=_deprecate_build_egg_parameter,
    help="[DEPRECATED] Only build the given egg, don't deploy it. "
    "Use `shub build-egg` instead",
)
@click.option("-v", "--verbose", help="Stream deploy logs to console", is_flag=True)
@click.option("-k", "--keep-log", help="Keep the deploy log", is_flag=True)
@click.option(
    "--ignore-size", help="Ignore deploy request's egg(s) size check", is_flag=True
)
def cli(target, version, debug, egg, build_egg, verbose, keep_log, ignore_size):
    if build_egg is not None:
        build_egg_cmd(build_egg, debug)
        return
    conf = load_shub_config()
    create_scrapinghub_yml_wizard(conf, target=target)
    image = conf.get_target_conf(target).image
    if not image:
        deploy_cmd(target, version, debug, egg, verbose, keep_log, conf=conf)
    elif image.startswith(SH_IMAGES_REGISTRY):
        upload_cmd(target, version)
    else:
        raise BadParameterException(
            "Please use `shub image` commands to work with Docker registries "
            "other than Scrapinghub default registry."
        )


def deploy_cmd(target, version, debug, egg, verbose, keep_log, conf=None):
    egg = egg and str(Path(egg).absolute())
    with _project_cwd():
        _deploy_cmd(target, version, debug, egg, verbose, keep_log, conf)


def _deploy_cmd(target, version, debug, egg, verbose, keep_log, conf):
    tmpdir = None
    try:
        conf = conf or load_shub_config()
        targetconf = conf.get_target_conf(target)
        version = version or targetconf.version
        auth = (targetconf.apikey, "")

        if egg:
            click.echo(f"Using egg: {egg}")
        else:
            click.echo(f"Packing version {version}")
            egg, tmpdir = build_project_egg()

        _upload_egg(
            targetconf.endpoint,
            egg,
            targetconf.project_id,
            version,
            auth,
            verbose,
            keep_log,
            targetconf.stack,
            targetconf.requirements_file,
            targetconf.eggs,
        )
        click.echo(
            f"Run your spiders at: https://app.zyte.com/p/{targetconf.project_id}/"
        )
    finally:
        remove_build_dir(tmpdir, debug)


def _url(endpoint, action):
    return urljoin(endpoint, action)


def _upload_egg(
    endpoint,
    eggpath,
    project,
    version,
    auth,
    verbose,
    keep_log,
    stack=None,
    requirements_file=None,
    eggs=None,
):
    expanded_eggs = []
    for e in eggs or []:
        # Expand glob patterns, but make sure we don't swallow non-existing
        # eggs that were directly named
        # (glob.glob('non_existing_file') returns [])
        if any(["*" in e, "?" in e, "[" in e and "]" in e]):
            # Never match the main egg
            expanded_eggs.extend(
                [
                    x
                    for x in glob.glob(e)  # noqa: PTH207
                    if Path(x).resolve() != Path(eggpath).resolve()
                ]
            )
        else:
            expanded_eggs.append(e)

    data = {"project": project, "version": version}
    if stack:
        data["stack"] = stack

    try:
        files = [("eggs", open(path, "rb")) for path in expanded_eggs]  # noqa: PTH123
        if _is_pipfile(requirements_file):
            requirements_file = _get_pipfile_requirements()
        elif _is_poetry(requirements_file):
            requirements_file = _get_poetry_requirements()
        elif requirements_file:
            requirements_file = open(requirements_file, "rb")  # noqa: PTH123
        if requirements_file:
            files.append(("requirements", requirements_file))
    except OSError as e:
        raise ShubException(f"{e.strerror} {e.filename}") from e
    files.append(("egg", Path(eggpath).open("rb")))
    url = _url(endpoint, "scrapyd/addversion.json")
    click.echo(f'Deploying to Scrapy Cloud project "{project}"')
    return make_deploy_request(url, data, files, auth, verbose, keep_log)


def _is_pipfile(name):
    return name in ["Pipfile", "Pipfile.lock"]


def _get_pipfile_requirements():
    executable = shutil.which("pipenv")
    if executable is None:
        raise NotFoundException("You need pipenv installed to deploy with Pipfile")
    if not Path("Pipfile.lock").exists():
        raise ShubException("Please lock your Pipfile before deploying")
    requirements = run_cmd([executable, "requirements"])
    # Scrapy Cloud does not support editable packages
    return "\n".join(line.removeprefix("-e ") for line in requirements.splitlines())


def _is_poetry(name):
    if name != "pyproject.toml":
        return False
    data = toml.load(name)
    return "poetry" in (data.get("tool") or {})


def _get_poetry_requirements_fallback():
    data = toml.load("poetry.lock")
    # Adapted from poetry 1.0.0a2 poetry/utils/exporter.py
    lines = []
    for package in data["package"]:
        source = package.get("source") or {}
        source_type = source.get("type")
        if source_type == "git":
            line = "git+{}@{}#egg={}".format(
                source["url"], source["reference"], package["name"]
            )
        elif source_type in ["directory", "file"]:
            line = ""
            line += source["url"]
        else:
            line = "{}=={}".format(package["name"], package["version"])

            if source_type == "legacy" and source["url"]:
                line += " \\\n"
                line += "    --index-url {}".format(source["url"])

        line += "\n"
        lines.append(line)
    return "".join(lines)


def _get_poetry_requirements():
    executable = shutil.which("poetry")
    if executable is None:
        try:
            return _get_poetry_requirements_fallback()
        except Exception as e:
            raise NotFoundException("poetry executable not found.") from e
    try:
        return run_cmd(
            [executable, "export", "--without-hashes", "-f", "requirements.txt"]
        )
    except SubcommandException as original_exception:
        try:
            return _get_poetry_requirements_fallback()
        except Exception as fallback_exception:
            raise original_exception from fallback_exception
