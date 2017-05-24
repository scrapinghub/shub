import os
import zipfile

import mock
import pytest
import requests
import yaml
from click.testing import CliRunner

from shub.bootstrap import cli, EXAMPLE_REPO, list_projects, unzip_project
from shub.exceptions import (
    BadParameterException, NotFoundException, RemoteErrorException)


BOOTSTRAP_PROJECTS = """
projA:
    path: projects_dir/projA
    description: PROJECT_A_DESC

projB:
    path: projects_dir/projB
    description: PROJECT_B_DESC
"""


REPO_ZIP_PATH = os.path.join(os.path.dirname(__file__), 'samples',
                             'custom-images-examples-master.zip')


@pytest.fixture
def requests_get_mock():
    with mock.patch('shub.bootstrap.requests.get') as m:
        yield m


@pytest.fixture
def github_responses(requests_get_mock):
    requests_get_mock.return_value.text = BOOTSTRAP_PROJECTS
    with open(REPO_ZIP_PATH, 'rb') as f:
        requests_get_mock.return_value.content = f.read()


def test_list_projects(capsys):
    projects = yaml.safe_load(BOOTSTRAP_PROJECTS)
    list_projects(projects)
    out, _ = capsys.readouterr()
    assert 'projA' in out
    assert 'PROJECT_A_DESC' in out
    assert 'projB' in out
    assert 'PROJECT_B_DESC' in out
    assert 'projects_dir' not in out


def test_unzip_project(tempdir):
    target_dir = str(tempdir.join('projA'))
    project = {'path': 'projects_dir/projA'}
    repo_zip = zipfile.ZipFile(REPO_ZIP_PATH)
    assert not os.path.exists(target_dir)
    unzip_project(repo_zip, project, target_dir)
    assert os.path.exists(target_dir)
    assert os.path.isfile(os.path.join(target_dir, 'a_file'))
    assert os.path.isdir(os.path.join(target_dir, 'a_dir'))
    assert os.path.isfile(os.path.join(target_dir, 'a_dir', 'a_dir_file'))


@pytest.mark.usefixtures('github_responses')
def test_cli_lists_projects():
    result = CliRunner().invoke(cli, ['-l'])
    assert result.exit_code == 0
    assert 'projA' in result.output
    assert 'PROJECT_A_DESC' in result.output


@pytest.mark.usefixtures('github_responses')
def test_cli_clones_project_into_default_dir(tempdir):
    target_dir = str(tempdir.join('projA'))
    assert not os.path.exists(target_dir)
    result = CliRunner().invoke(cli, ['projA'])
    assert result.exit_code == 0
    assert os.path.isdir(target_dir)
    assert os.path.isfile(os.path.join(target_dir, 'a_file'))


@pytest.mark.usefixtures('github_responses')
def test_cli_clones_project_into_target_dir(tempdir):
    target_dir = str(tempdir.join('target_dir'))
    assert not os.path.exists(target_dir)
    result = CliRunner().invoke(cli, ['projA', 'target_dir'])
    assert result.exit_code == 0
    assert os.path.isdir(target_dir)
    assert os.path.isfile(os.path.join(target_dir, 'a_file'))


def test_cli_fails_on_existing_target_dir(tempdir):
    os.mkdir('target_dir')
    result = CliRunner().invoke(cli, ['some_project', 'target_dir'])
    assert result.exit_code == BadParameterException.exit_code
    assert "exists" in result.output


@pytest.mark.usefixtures('github_responses')
def test_cli_fails_on_unknown_project():
    result = CliRunner().invoke(cli, ['nonexistent'])
    assert result.exit_code == NotFoundException.exit_code
    assert "shub bootstrap -l" in result.output


def test_cli_links_to_repo_on_http_error(requests_get_mock):
    requests_get_mock.return_value.raise_for_status.side_effect = (
        requests.HTTPError)
    result = CliRunner().invoke(cli, ['some_project'])
    assert result.exit_code == RemoteErrorException.exit_code
    assert EXAMPLE_REPO in result.output
