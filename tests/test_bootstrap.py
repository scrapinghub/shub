import zipfile
from pathlib import Path
from unittest import mock

import pytest
import requests
import yaml
from click.testing import CliRunner

from shub.bootstrap import EXAMPLE_REPO, cli, list_projects, unzip_project
from shub.exceptions import (
    BadParameterException,
    NotFoundException,
    RemoteErrorException,
)

BOOTSTRAP_PROJECTS = """
projA:
    path: projects_dir/projA
    description: PROJECT_A_DESC

projB:
    path: projects_dir/projB
    description: PROJECT_B_DESC
"""


REPO_ZIP_PATH = Path(__file__).parent / "samples" / "custom-images-examples-master.zip"


@pytest.fixture
def requests_get_mock():
    with mock.patch("shub.bootstrap.requests.get") as m:
        yield m


@pytest.fixture
def github_responses(requests_get_mock):
    requests_get_mock.return_value.text = BOOTSTRAP_PROJECTS
    with REPO_ZIP_PATH.open("rb") as f:
        requests_get_mock.return_value.content = f.read()


def test_list_projects(capsys):
    projects = yaml.safe_load(BOOTSTRAP_PROJECTS)
    list_projects(projects)
    out, _ = capsys.readouterr()
    assert "projA" in out
    assert "PROJECT_A_DESC" in out
    assert "projB" in out
    assert "PROJECT_B_DESC" in out
    assert "projects_dir" not in out


def test_unzip_project(tempdir):
    target_dir = Path(tempdir, "projA")
    project = {"path": "projects_dir/projA"}
    repo_zip = zipfile.ZipFile(REPO_ZIP_PATH)
    assert not target_dir.exists()
    unzip_project(repo_zip, project, target_dir)
    assert target_dir.exists()
    assert (target_dir / "a_file").is_file()
    assert (target_dir / "a_dir").is_dir()
    assert (target_dir / "a_dir" / "a_dir_file").is_file()


@pytest.mark.parametrize(
    "relative_path", [None, "../victim", "projects_dir/../../victim"]
)
def test_unzip_project_rejects_paths_outside_the_archive(tempdir, relative_path):
    victim = Path(tempdir, "victim")
    victim.mkdir()
    (victim / "data").touch()
    path = str(victim) if relative_path is None else relative_path
    target_dir = Path(tempdir, "target")
    with pytest.raises(RemoteErrorException):
        unzip_project(zipfile.ZipFile(REPO_ZIP_PATH), {"path": path}, target_dir)
    assert (victim / "data").is_file()
    assert not target_dir.exists()


@pytest.mark.usefixtures("github_responses")
def test_cli_lists_projects():
    result = CliRunner().invoke(cli, ["-l"])
    assert result.exit_code == 0
    assert "projA" in result.output
    assert "PROJECT_A_DESC" in result.output


@pytest.mark.usefixtures("github_responses")
def test_cli_clones_project_into_default_dir(tempdir):
    target_dir = Path(tempdir, "projA")
    assert not target_dir.exists()
    result = CliRunner().invoke(cli, ["projA"])
    assert result.exit_code == 0
    assert target_dir.is_dir()
    assert (target_dir / "a_file").is_file()


@pytest.mark.usefixtures("github_responses")
def test_cli_clones_project_into_target_dir(tempdir):
    target_dir = Path(tempdir, "target_dir")
    assert not target_dir.exists()
    result = CliRunner().invoke(cli, ["projA", "target_dir"])
    assert result.exit_code == 0
    assert target_dir.is_dir()
    assert (target_dir / "a_file").is_file()


def test_cli_fails_on_existing_target_dir(tempdir):
    Path("target_dir").mkdir()
    result = CliRunner().invoke(cli, ["some_project", "target_dir"])
    assert result.exit_code == BadParameterException.exit_code
    assert "exists" in result.output


@pytest.mark.usefixtures("github_responses")
def test_cli_fails_on_unknown_project():
    result = CliRunner().invoke(cli, ["nonexistent"])
    assert result.exit_code == NotFoundException.exit_code
    assert "shub bootstrap -l" in result.output


def test_cli_links_to_repo_on_http_error(requests_get_mock):
    requests_get_mock.return_value.raise_for_status.side_effect = requests.HTTPError
    result = CliRunner().invoke(cli, ["some_project"])
    assert result.exit_code == RemoteErrorException.exit_code
    assert EXAMPLE_REPO in result.output
