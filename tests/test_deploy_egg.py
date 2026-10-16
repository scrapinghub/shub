import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from zipfile import ZipFile

import pytest

from shub import deploy_egg
from shub.exceptions import BadParameterException


class FakeRequester:
    """Used to mock shub.utils#make_deploy_request"""

    def fake_request(self, *args):
        self.url = args[0]
        self.data = args[1]
        self.files = args[2]
        self.auth = args[3]


@mock.patch.dict(os.environ, {"SHUB_APIKEY": "1234"})
class TestDeployEgg(unittest.TestCase):
    def setUp(self):
        self.curdir = Path.cwd()
        self.fake_requester = FakeRequester()
        deploy_egg.utils.make_deploy_request = self.fake_requester.fake_request
        self.tmp_dir = tempfile.mkdtemp(prefix="shub-test-deploy-eggs")

    def tearDown(self):
        os.chdir(self.curdir)
        if Path(self.tmp_dir).exists():
            shutil.rmtree(self.tmp_dir)

    def test_parses_project_information_correctly(self):
        # this test's assertions are based on the values
        # defined on this folder's setup.py file
        shutil.rmtree(self.tmp_dir)
        shutil.copytree("tests/samples/deploy_egg_sample_project", self.tmp_dir)
        os.chdir(self.tmp_dir)

        data = self.call_main_and_check_request_data()
        assert "1.2.0" == data["version"]

    def test_can_clone_a_git_repo_and_deploy_the_egg(self):
        self._unzip_git_repo_to(self.tmp_dir)
        repo = str(Path(self.tmp_dir, "deploy_egg_sample_repo.git"))

        self.call_main_and_check_request_data(from_url=repo)
        data = self.call_main_and_check_request_data()

        assert "master" in data["version"]

    @unittest.skip("flaky")
    def test_can_deploy_an_egg_from_pypi(self):
        pkg = str(Path("tests/samples/deploy_egg_sample_project.zip").resolve())
        self.call_main_and_check_request_data(from_pypi=pkg)

    def test_can_clone_checkout_and_deploy_the_egg(self):
        self._unzip_git_repo_to(self.tmp_dir)
        repo = str(Path(self.tmp_dir, "deploy_egg_sample_repo.git"))

        branch = "dev"
        data = self.call_main_and_check_request_data(from_url=repo, git_branch=branch)
        assert "dev" in data["version"]

    def test_fails_on_invalid_repo(self):
        self._unzip_git_repo_to(self.tmp_dir)
        repo = str(Path(self.tmp_dir, "deploy_egg_sample_repo.git"))
        shutil.rmtree(Path(repo, ".git"))

        with pytest.raises(BadParameterException):
            self.call_main_and_check_request_data(from_url=repo)

    def test_fails_on_invalid_branch(self):
        self._unzip_git_repo_to(self.tmp_dir)
        repo = str(Path(self.tmp_dir, "deploy_egg_sample_repo.git"))
        with pytest.raises(BadParameterException):
            self.call_main_and_check_request_data(
                from_url=repo, git_branch="nonexisting"
            )

    def _unzip_git_repo_to(self, path):
        zipped_repo = Path("tests/samples/deploy_egg_sample_repo.git.zip").resolve()
        ZipFile(zipped_repo).extractall(path)

    def call_main_and_check_request_data(
        self, project_id=0, from_url=None, git_branch=None, from_pypi=None
    ):
        # WHEN
        deploy_egg.main(project_id, from_url, git_branch, from_pypi)

        data = self.fake_requester.data
        files = self.fake_requester.files

        # THEN
        # the egg was successfully built, let's check the data
        # that is sent to the scrapy cloud
        assert "test_project" in files["egg"][0]
        assert project_id == data["project"]
        assert "test_project" == data["name"]

        return data
