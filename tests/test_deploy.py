import os
import platform
import re
import shutil
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
import yaml
from cleo.testers.command_tester import CommandTester
from click.testing import CliRunner
from packaging.version import parse

from shub import deploy
from shub.build_egg import build_project_egg
from shub.exceptions import (
    BadParameterException,
    DeployRequestTooLargeException,
    NotFoundException,
    ShubException,
)
from shub.utils import _SETUP_PY_TEMPLATE, STDOUT_ENCODING, create_default_setup_py

from .utils import (
    VALID_SCRAPY_CFG,
    AssertInvokeRaisesMixin,
    make_git_project,
    mock_conf,
)

try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:
    POETRY_VERSION = None
else:
    try:
        POETRY_VERSION = parse(version("poetry"))
    except PackageNotFoundError:
        try:
            POETRY_VERSION = parse(version("poetry-core"))
        except PackageNotFoundError:
            POETRY_VERSION = None

# What the (mocked) stack lookup returns
LATEST_STACK = "scrapy:2.99-20990101"


class DeployTest(AssertInvokeRaisesMixin, unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.conf = mock_conf(self, "shub.deploy.load_shub_config")

    def _make_project(self):
        with Path("scrapy.cfg").open("w") as f:
            f.write(VALID_SCRAPY_CFG)

    @patch("shub.deploy.make_deploy_request")
    def test_detect_scrapy_project(self, mock_deploy_req):
        with self.runner.isolated_filesystem():
            self.assertInvokeRaises(NotFoundException, deploy.cli)
            self._make_project()
            result = self.runner.invoke(deploy.cli)
            assert 0 == result.exit_code

    @patch("shub.deploy.make_deploy_request")
    def _invoke_with_project(self, args, mock_deploy_req):
        with self.runner.isolated_filesystem():
            self._make_project()
            self.runner.invoke(deploy.cli, args)
        return mock_deploy_req.call_args[0]

    def test_fallback_to_default(self):
        url, data, _files, auth, _, _ = self._invoke_with_project(None)
        assert self.conf.endpoints["default"] in url
        assert data == {"project": 1, "version": "version"}
        assert auth == (self.conf.apikeys["default"], "")

    def test_with_target(self):
        url, data, _files, auth, _, _ = self._invoke_with_project(("prod",))
        assert self.conf.endpoints["default"] in url
        assert data == {"project": 2, "version": "version"}
        assert auth == (self.conf.apikeys["default"], "")

    def test_with_id(self):
        url, data, _files, auth, _, _ = self._invoke_with_project(("123",))
        assert self.conf.endpoints["default"] in url
        assert data == {"project": 123, "version": "version"}
        assert auth == (self.conf.apikeys["default"], "")

    def test_with_external_id(self):
        url, data, _files, auth, _, _ = self._invoke_with_project(("vagrant/456",))
        assert self.conf.endpoints["vagrant"] in url
        assert data == {"project": 456, "version": "version"}
        assert auth == (self.conf.apikeys["vagrant"], "")

    @patch("shub.deploy.build_project_egg")
    @patch("shub.deploy.make_deploy_request")
    def test_deploys_given_egg(self, mock_deploy_req, mock_build):
        with self.runner.isolated_filesystem():
            self._make_project()
            with Path("given.egg").open("w") as f:
                f.write("egg content")
            given_egg = str(Path("given.egg").absolute())
            result = self.runner.invoke(deploy.cli, ("--egg", "given.egg"))
            assert 0 == result.exit_code, result.output
            name, egg = mock_deploy_req.call_args[0][2][-1]
            egg.close()
        assert f"Using egg: {given_egg}" in result.output
        assert ("egg", given_egg) == (name, egg.name)
        mock_build.assert_not_called()

    @patch("shub.deploy.make_deploy_request")
    def test_build_egg_flag_builds_egg_without_deploying(self, mock_deploy_req):
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(deploy.cli, ("--build-egg", "built.egg"))
            assert 0 == result.exit_code, result.output
            assert "Writing egg to built.egg" in result.output
            assert zipfile.is_zipfile("built.egg")
        mock_deploy_req.assert_not_called()

    def test_build_egg_flag_is_deprecated(self):
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(deploy.cli, ("--build-egg", "built.egg"))
        assert 0 == result.exit_code, result.output
        assert (
            "WARNING: --build-egg parameter is deprecated. Please use `shub build-egg FILENAME` instead."
            in result.output
        )

    @patch("shub.deploy.make_deploy_request")
    def test_deploying_does_not_warn_about_build_egg(self, mock_deploy_req):
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(deploy.cli)
        assert 0 == result.exit_code, result.output
        assert "deprecated" not in result.output

    @patch("requests.sessions.Session.send")
    @patch("shub.deploy.upload_cmd")
    @patch("shub.deploy.deploy_cmd")
    @patch("shub.deploy.make_deploy_request")
    @patch("shub.deploy.load_shub_config")
    @patch("shub.deploy.create_scrapinghub_yml_wizard")
    def test_build_egg_flag_is_handled_before_deploying(
        self,
        mock_wizard,
        mock_load_conf,
        mock_deploy_req,
        mock_deploy_cmd,
        mock_upload_cmd,
        mock_send,
    ):
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(deploy.cli, ("--build-egg", "built.egg"))
            assert 0 == result.exit_code, result.output
            assert Path("built.egg").is_file()
            # Neither the wizard nor anything else touches the configuration
            assert not Path("scrapinghub.yml").exists()
        # No target or API key is needed, and nothing is deployed
        mock_load_conf.assert_not_called()
        mock_wizard.assert_not_called()
        mock_deploy_cmd.assert_not_called()
        mock_deploy_req.assert_not_called()
        mock_upload_cmd.assert_not_called()
        mock_send.assert_not_called()

    @patch("shub.deploy.upload_cmd")
    def test_build_egg_flag_with_custom_image_target(self, mock_upload_cmd):
        # The flag used to be silently ignored for targets that use a custom
        # image, and the image was uploaded instead
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(
                deploy.cli, ("custom2", "--build-egg", "built.egg")
            )
            assert 0 == result.exit_code, result.output
            assert zipfile.is_zipfile("built.egg")
        mock_upload_cmd.assert_not_called()

    def test_build_egg_flag_debug(self):
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(
                deploy.cli, ("--build-egg", "built.egg", "--debug")
            )
        assert 0 == result.exit_code, result.output
        match = re.search(
            r"^Output dir not removed: (.+)$", result.output, re.MULTILINE
        )
        assert match is not None, result.output
        build_dir = match.group(1)
        self.addCleanup(shutil.rmtree, build_dir, ignore_errors=True)
        assert Path(build_dir).is_dir()

    def test_build_egg_flag_requires_a_scrapy_project(self):
        with self.runner.isolated_filesystem():
            self.assertInvokeRaises(
                NotFoundException, deploy.cli, ("--build-egg", "built.egg")
            )
            assert not Path("built.egg").exists()

    def test_build_egg_flag_filename_must_not_be_a_directory(self):
        with self.runner.isolated_filesystem():
            self._make_project()
            Path("built.egg").mkdir()
            result = self.runner.invoke(deploy.cli, ("--build-egg", "built.egg"))
        assert 2 == result.exit_code
        assert "is a directory" in result.output

    def test_previous_build_egg_name_still_works(self):
        # Deploy wrappers built on top of shub import it from shub.deploy
        assert build_project_egg is deploy._build_egg

    @patch("shub.utils.get_latest_scrapy_stack", return_value=LATEST_STACK)
    @patch("shub.utils.has_project_access", return_value=True)
    @patch("shub.deploy.make_deploy_request")
    def test_new_config_uses_latest_stack(
        self, mock_deploy_req, mock_access, mock_latest_stack
    ):
        self.conf.projects.clear()
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(deploy.cli, input="12345\n")
            sh_yml = yaml.safe_load(Path("scrapinghub.yml").read_text())
        assert result.exit_code == 0
        assert sh_yml == {"project": 12345, "stack": LATEST_STACK}
        # The deploy that generated the config already uses the stack
        _, data, _, _, _, _ = mock_deploy_req.call_args[0]
        assert data == {
            "project": 12345,
            "version": "version",
            "stack": LATEST_STACK,
        }

    @patch("shub.utils.get_latest_scrapy_stack")
    @patch("shub.deploy.make_deploy_request")
    def test_existing_config_without_stack_is_untouched(
        self, mock_deploy_req, mock_latest_stack
    ):
        original_sh_yml = "project: 1\n"
        with self.runner.isolated_filesystem():
            self._make_project()
            Path("scrapinghub.yml").write_text(original_sh_yml)
            result = self.runner.invoke(deploy.cli)
            assert Path("scrapinghub.yml").read_text() == original_sh_yml
        assert result.exit_code == 0
        _, data, _, _, _, _ = mock_deploy_req.call_args[0]
        assert data == {"project": 1, "version": "version"}
        mock_latest_stack.assert_not_called()

    def test_deploy_list_targets(self):
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(deploy.cli, ("--list-targets",))
            assert result.exit_code == 0

    @patch("shub.deploy.deploy_cmd")
    def test_custom_deploy_disabled(self, mock_deploy_cmd):
        with self.runner.isolated_filesystem():
            self._make_project()
            self.runner.invoke(deploy.cli, ("custom1",))
        assert mock_deploy_cmd.called

    @patch("shub.deploy.upload_cmd")
    def test_custom_deploy_default(self, mock_upload_cmd):
        with self.runner.isolated_filesystem():
            self._make_project()
            self.runner.invoke(deploy.cli, ("custom2",))
        assert mock_upload_cmd.call_args[0] == ("custom2", None)

    @patch("shub.deploy.upload_cmd")
    def test_custom_deploy_by_id(self, mock_upload_cmd):
        with self.runner.isolated_filesystem():
            self._make_project()
            self.runner.invoke(deploy.cli, ("5",))
        mock_upload_cmd.assert_called_once_with("5", None)

    def test_custom_deploy_bad_registry(self):
        with self.runner.isolated_filesystem():
            self._make_project()
            self.assertInvokeRaises(BadParameterException, deploy.cli, ("custom3",))

    @patch("shub.deploy.make_deploy_request")
    def test_deploy_with_custom_setup_py(self, mock_deploy_req):
        with self.runner.isolated_filesystem():
            # This scrapy.cfg contains no "settings" section, so creating a
            # default setup.py would fail (because we can't find the settings
            # module)
            Path("scrapy.cfg").open("w").close()
            # However, we already have a setup.py...
            create_default_setup_py(settings="some_module")
            # ... so shub should not fail while trying to create one
            result = self.runner.invoke(deploy.cli)
            assert result.exit_code == 0

    @patch("shub.utils.requests")
    @patch("shub.utils.write_and_echo_logs")
    def test_deploy_with_single_large_file(self, mock_logs, mock_requests):
        with self.runner.isolated_filesystem():
            self._make_project()
            # patch setup_py to include package data files
            setup_py = _SETUP_PY_TEMPLATE % {"settings": "project.settings"}
            setup_py = setup_py.rsplit("\n", 2)[0]  # drop an enclosing brace
            setup_py += "    include_package_data = True)"
            with Path("setup.py").open("w") as setup_file:
                setup_file.write(setup_py)
            # create a fake package and add a large random file there
            Path("files").mkdir()
            Path("files/__init__.py").touch()
            with Path("files/file.large").open("wb") as bigfile:
                bigfile.write(os.urandom(50 * 1024 * 1024))
            # add manifest to include the non-code file
            with Path("MANIFEST.in").open("w") as manifest_f:
                manifest_f.write("include files/file.large")
            fake_response = requests.Response()
            fake_response.status_code = 200
            mock_requests.post.return_value = fake_response
            self.assertInvokeRaises(DeployRequestTooLargeException, deploy.cli)


class GitFilteredBuildTest(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.conf = mock_conf(self, "shub.deploy.load_shub_config")
        if shutil.which("git") is None:
            self.skipTest("git executable not found")

    @patch("shub.deploy.make_deploy_request")
    def test_deploy_default_from_git_repo(self, mock_deploy_req):
        with self.runner.isolated_filesystem():
            make_git_project()
            result = self.runner.invoke(deploy.cli)
            assert 0 == result.exit_code, result.output

    @patch("shub.deploy.make_deploy_request")
    def test_deploy_from_subdir(self, mock_deploy_req):
        with self.runner.isolated_filesystem():
            make_git_project()
            os.chdir("project")
            result = self.runner.invoke(deploy.cli)
            assert 0 == result.exit_code, result.output
        mock_deploy_req.assert_called_once()


class DeployFilesTest(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.request = patch("shub.deploy.make_deploy_request").start()
        self.addCleanup(patch.stopall)

    def _deploy(self, main_egg="./main.egg", req="./requirements.txt", eggs=None):
        if eggs is None:
            eggs = ["./1.egg", "./2.egg"]

        deploy._upload_egg(
            "endpoint",
            main_egg,
            "1",
            "version",
            "auth",
            False,
            False,
            requirements_file=req,
            eggs=eggs,
        )
        files = {}
        for name, file in self.request.call_args[0][2]:
            files.setdefault(name, []).append(
                file if isinstance(file, str) else file.read().decode("utf-8")
            )

        return files

    def test_correct_files(self):
        with self.runner.isolated_filesystem():
            with Path("./main.egg").open("w") as f:
                f.write("main content")
            with Path("./requirements.txt").open("w") as f:
                f.write("requirements content")
            with Path("./1.egg").open("w") as f:
                f.write("1.egg content")
            with Path("./2.egg").open("w") as f:
                f.write("2.egg content")
            files = self._deploy()

        assert files["egg"][0] == "main content"
        assert files["requirements"][0] == "requirements content"
        assert files["eggs"][0] == "1.egg content"
        assert files["eggs"][1] == "2.egg content"

    def test_no_egg(self):
        with self.runner.isolated_filesystem():
            with Path("./main.egg").open("w") as f:
                f.write("main content")
            with Path("./requirements.txt").open("w") as f:
                f.write("requirements content")
            with Path("./1.egg").open("w") as f:
                f.write("1.egg content")

            with pytest.raises(ShubException) as cm:
                self._deploy()

            assert cm.value.message == "No such file or directory ./2.egg"

    def test_no_requirements(self):
        with self.runner.isolated_filesystem():
            with Path("./main.egg").open("w") as f:
                f.write("main content")
            with Path("./1.egg").open("w") as f:
                f.write("1.egg content")
            with Path("./2.egg").open("w") as f:
                f.write("2.egg content")

            with pytest.raises(ShubException) as cm:
                self._deploy()

            assert cm.value.message == "No such file or directory ./requirements.txt"

    def test_egg_glob_pattern(self):
        with self.runner.isolated_filesystem():
            with Path("./main.egg").open("w") as f:
                f.write("main content")
            with Path("./a1.egg").open("w") as f:
                f.write("a1.egg content")
            with Path("./a2.egg").open("w") as f:
                f.write("a2.egg content")
            with Path("./b3.egg").open("w") as f:
                f.write("b3.egg content")
            files_a = self._deploy(eggs=["./a*.egg"], req=None)
            files_c = self._deploy(eggs=["./c*.egg"], req=None)
            files_all = self._deploy(eggs=["./*.egg"], req=None)
            files_main = self._deploy(eggs=["./main.egg", "./*.egg"], req=None)

        assert len(files_a["eggs"]) == 2
        assert "a1.egg content" in files_a["eggs"]
        assert "a2.egg content" in files_a["eggs"]
        assert "eggs" not in files_c

        # main egg should not be added to eggs even it it matches glob pattern
        assert len(files_all["eggs"]) == 3
        assert "a1.egg content" in files_all["eggs"]
        assert "a2.egg content" in files_all["eggs"]
        assert "b3.egg content" in files_all["eggs"]

        # but do upload the main egg if it's directly requested
        assert len(files_main["eggs"]) == 4
        assert "main content" in files_main["eggs"]

    def pipfile_test(self, req_name):
        with self.runner.isolated_filesystem():
            with Path("./main.egg").open("w") as f:
                f.write("main content")
            with Path("./Pipfile.lock").open("w") as f:
                f.write("""
                {
                    "_meta": {
                        "sources": [
                            {
                                "name": "pypi",
                                "url": "https://pypi.python.org/simple",
                                "verify_ssl": true
                            },
                            {
                                "name": "external-index",
                                "url": "https://example.external-index.org/simple",
                                "verify_ssl": true
                            }
                        ]
                    },
                    "default": {
                        "package": {
                            "version": "==0.0.0"
                        },
                        "hash-package": {
                            "version": "==0.0.1",
                            "hash": "hash"
                        },
                        "hash-package2": {
                            "version": "==0.0.1",
                            "hashes": ["hash1", "hash2"]
                        },
                        "vcs-package": {
                            "git": "https://github.com/vcs/package.git",
                            "ref": "master",
                            "editable": true
                        }
                    }
                }
                """)
            with Path("./1.egg").open("w") as f:
                f.write("1.egg content")
            with Path("./2.egg").open("w") as f:
                f.write("2.egg content")
            files = self._deploy(req=req_name)

        reqs = set(files["requirements"][0].split("\n"))
        assert reqs == {
            "-i https://pypi.python.org/simple",
            "--extra-index-url https://example.external-index.org/simple",
            "package==0.0.0",
            "hash-package==0.0.1",
            "hash-package2==0.0.1",
            "git+https://github.com/vcs/package.git@master#egg=vcs-package",
        }

    def test_pipfile_names(self):
        self.pipfile_test("Pipfile")
        self.pipfile_test("Pipfile.lock")

    def test_pipfile_lock_missing(self):
        with self.runner.isolated_filesystem():
            with Path("./main.egg").open("w") as f:
                f.write("main content")
            with Path("./1.egg").open("w") as f:
                f.write("1.egg content")
            with Path("./2.egg").open("w") as f:
                f.write("2.egg content")

            with pytest.raises(ShubException) as cm:
                self._deploy(req="Pipfile")

            assert cm.value.message == "Please lock your Pipfile before deploying"

    @patch("shub.deploy.shutil.which", return_value=None)
    def test_pipenv_missing(self, mock_which):
        with self.runner.isolated_filesystem():
            with Path("./main.egg").open("w") as f:
                f.write("main content")
            with Path("./1.egg").open("w") as f:
                f.write("1.egg content")
            with Path("./2.egg").open("w") as f:
                f.write("2.egg content")

            with pytest.raises(NotFoundException) as cm:
                self._deploy(req="Pipfile")

            assert (
                cm.value.message == "You need pipenv installed to deploy with Pipfile"
            )

    @patch("subprocess.check_output")
    def test_poetry_2_or_higher(self, mock_check_output):
        if not POETRY_VERSION or POETRY_VERSION < parse("2"):
            raise self.skipTest("poetry or poetry-core >=2 is not installed")

        from poetry.console.application import Application  # noqa: PLC0415
        from poetry_plugin_export.command import ExportCommand  # noqa: PLC0415

        with patch("poetry.packages.locker.Locker.is_fresh") as mock_is_fresh:
            with self.runner.isolated_filesystem():
                with Path("./main.egg").open("w") as f:
                    f.write("main content")
                with Path("./pyproject.toml").open("w") as f:
                    f.write("""
                    [project]
                    name = "test_project"
                    version = "1.2.0"
                    [tool.poetry]
                    [tool.poetry.requires-plugins]
                    poetry-plugin-export = ">=1.8"
                    """)
                with Path("./poetry.lock").open("w") as f:
                    f.write("""
                    [[package]]
                    name = "package"
                    version = "0.0.0"
                    optional = false
                    python-versions = "*"
                    groups = ["main"]
                    files = []
                    [[package]]
                    name = "vcs-package"
                    version = "0.0.1"
                    optional = false
                    python-versions = "*"
                    groups = ["main"]
                    files = []
                    [package.source]
                    reference = "master"
                    type = "git"
                    url = "https://github.com/vcs/package.git"
                    [[package]]
                    name = "file-package"
                    version = "0.0.1"
                    optional = false
                    python-versions = "*"
                    groups = ["main"]
                    files = []
                    [package.source]
                    reference = ""
                    type = "file"
                    url = "/path/to/package.tar.gz"
                    [[package]]
                    name = "dir-package"
                    version = "0.0.1"
                    optional = false
                    python-versions = "*"
                    groups = ["main"]
                    files = []
                    [package.source]
                    reference = ""
                    type = "directory"
                    url = "/path/to/package"
                    [metadata.hashes]
                    package = ["hash"]
                    vcs-package = ["hash1"]
                    [metadata]
                    lock-version = "2.1"
                    """)
                with Path("./1.egg").open("w") as f:
                    f.write("1.egg content")
                with Path("./2.egg").open("w") as f:
                    f.write("2.egg content")

                # Skip check if lockfile is in sync with pyproject.toml
                mock_is_fresh.return_value = True

                def mock_check_output_side_effect(cmd, *args, **kwargs):
                    application = Application()
                    application.add(ExportCommand())
                    cmd = application.find("export")
                    cmd_tester = CommandTester(cmd)
                    cmd_tester.execute("--format requirements.txt")
                    assert cmd_tester.status_code != 1, cmd_tester.io.fetch_error()
                    return cmd_tester.io.fetch_output().encode(STDOUT_ENCODING)

                mock_check_output.side_effect = mock_check_output_side_effect

                files = self._deploy(req="pyproject.toml")

            assert mock_is_fresh.called
            assert mock_check_output.called

            path_prefix = "C:/" if platform.system() == "Windows" else ""

            assert (
                files["requirements"][0]
                == f"dir-package @ file:///{path_prefix}path/to/package ; "
                'python_version == "2.7" or python_version >= "3.4"\n'
                f"file-package @ file:///{path_prefix}path/to/package.tar.gz ; "
                'python_version == "2.7" or python_version >= "3.4"\n'
                "package==0.0.0 ; "
                'python_version == "2.7" or python_version >= "3.4"\n'
                "vcs-package @ git+https://github.com/vcs/package.git@master ; "
                'python_version == "2.7" or python_version >= "3.4"'
            )

    def test_poetry_fallback(self):
        """A poetry.lock file should work even if the poetry configuration is
        invalid, with limitations like no marker support."""
        with self.runner.isolated_filesystem():
            with Path("./main.egg").open("w") as f:
                f.write("main content")
            with Path("./pyproject.toml").open("w") as f:
                f.write("""
                [tool.poetry]
                """)
            with Path("./poetry.lock").open("w") as f:
                f.write("""
                [[package]]
                name = "package"
                version = "0.0.0"

                [[package]]
                name = "vcs-package"
                version = "0.0.1"

                [package.source]
                reference = "master"
                type = "git"
                url = "https://github.com/vcs/package.git"

                [[package]]
                name = "file-package"
                version = "0.0.1"

                [package.source]
                reference = ""
                type = "file"
                url = "/path/to/package.tar.gz"

                [[package]]
                name = "dir-package"
                version = "0.0.1"

                [package.source]
                reference = ""
                type = "directory"
                url = "/path/to/package"

                [metadata.hashes]
                package = ["hash"]
                vcs-package = ["hash1"]
                """)
            with Path("./1.egg").open("w") as f:
                f.write("1.egg content")
            with Path("./2.egg").open("w") as f:
                f.write("2.egg content")
            files = self._deploy(req="pyproject.toml")

        reqs = set(files["requirements"][0].split("\n"))
        assert reqs == {
            "package==0.0.0",
            "git+https://github.com/vcs/package.git@master#egg=vcs-package",
            "/path/to/package",
            "/path/to/package.tar.gz",
            "",
        }

    def test_poetry_lock_missing(self):
        with self.runner.isolated_filesystem():
            with Path("./pyproject.toml").open("w") as f:
                f.write("""
                [tool.poetry]
                """)
            with Path("./main.egg").open("w") as f:
                f.write("main content")
            with Path("./1.egg").open("w") as f:
                f.write("1.egg content")
            with Path("./2.egg").open("w") as f:
                f.write("2.egg content")

            with pytest.raises(ShubException) as cm:
                self._deploy(req="pyproject.toml")

            try:
                version("poetry")
            except PackageNotFoundError:
                assert "poetry executable not found" in cm.value.message
            else:
                assert "The Poetry configuration is invalid" in cm.value.message
