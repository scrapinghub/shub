from pathlib import Path

import pytest
from click.testing import CliRunner

from shub.exceptions import BadConfigException
from shub.image.init import (
    _format_requirements,
    _format_system_deps,
    _format_system_env,
    _wrap,
    cli,
)

from .utils import add_fake_requirements


@pytest.fixture
def project_dir(project_dir):
    """Overriden project_dir fixture without Dockerfile"""
    Path(project_dir, "Dockerfile").unlink()
    return project_dir


def test_cli_default_settings(project_dir):
    dockerfile_path = Path(project_dir, "Dockerfile")
    assert not dockerfile_path.exists()
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    msg = f"Dockerfile is saved to {dockerfile_path}"
    assert msg in result.output
    assert dockerfile_path.exists()


@pytest.mark.usefixtures("project_dir")
def test_cli_list_recommended_reqs():
    runner = CliRunner()
    result = runner.invoke(cli, ["--list-recommended-reqs"])
    assert result.exit_code == 0
    assert "Recommended Python deps list:" in result.output


def test_cli_abort_if_dockerfile_exists(project_dir):
    dockerfile_path = Path(project_dir, "Dockerfile")
    dockerfile_path.touch()
    runner = CliRunner()
    result = runner.invoke(cli, [], input="yes\n")
    assert result.exit_code == 1
    assert "Found a Dockerfile in the project directory, aborting" in result.output
    assert dockerfile_path.read_text() == ""


def test_cli_create_setup_py(project_dir):
    setup_py_path = Path(project_dir, "setup.py")
    setup_py_path.unlink()
    runner = CliRunner()
    result = runner.invoke(cli, [], input="yes\n")
    assert result.exit_code == 0
    assert setup_py_path.is_file()


def test_wrap():
    short_cmd = "run short command wrapping another one short"
    assert _wrap(short_cmd) == short_cmd
    assert _wrap(short_cmd + " " + short_cmd) == (
        short_cmd
        + " "
        + " ".join(short_cmd.split()[:3])
        + " \\\n    "
        + " ".join(short_cmd.split()[3:])
    )


def test_format_system_deps():
    # no deps at all
    assert _format_system_deps("-", None) is None
    # base deps only
    assert _format_system_deps("a,b,cd", None) == (
        "RUN apt-get update -qq && \\\n"
        "    apt-get install -qy a b cd && \\\n"
        "    rm -rf /var/lib/apt/lists/*"
    )
    # base & additional deps only
    assert _format_system_deps("a,b,cd", "ef,hk,b") == (
        "RUN apt-get update -qq && \\\n"
        "    apt-get install -qy a b cd ef hk && \\\n"
        "    rm -rf /var/lib/apt/lists/*"
    )
    # additional deps only
    assert _format_system_deps("-", "ef,hk,b") == (
        "RUN apt-get update -qq && \\\n"
        "    apt-get install -qy b ef hk && \\\n"
        "    rm -rf /var/lib/apt/lists/*"
    )


def test_format_system_env():
    assert _format_system_env(None) == "ENV TERM xterm"
    assert _format_system_env("test.settings") == (
        "ENV TERM xterm\nENV SCRAPY_SETTINGS_MODULE test.settings"
    )


def test_format_requirements(project_dir):
    add_fake_requirements(project_dir)
    basereqs = Path(project_dir, "requirements.txt")
    basereqs.unlink(missing_ok=True)
    # use given requirements
    assert _format_requirements(Path.cwd(), "fake-requirements.txt") == (
        "COPY ./fake-requirements.txt /app/requirements.txt\n"
        "RUN pip install --no-cache-dir -r requirements.txt"
    )
    assert not basereqs.exists()
    # using base requirements
    assert _format_requirements(Path.cwd(), "requirements.txt") == (
        "COPY ./requirements.txt /app/requirements.txt\n"
        "RUN pip install --no-cache-dir -r requirements.txt"
    )
    assert basereqs.exists()
    basereqs.unlink()


def test_no_scrapy_cfg(project_dir):
    Path(project_dir, "scrapy.cfg").unlink()
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == BadConfigException.exit_code
    error_msg = (
        "Error: Cannot find Scrapy project settings. Please ensure that current "
        "directory contains scrapy.cfg with settings section, see example at "
        "https://doc.scrapy.org/en/latest/topics/commands.html#default-structure-of-scrapy-projects"
    )
    assert error_msg in result.output
    assert not Path(project_dir, "Dockerfile").exists()
