import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from shub import build_egg
from shub.exceptions import NotFoundException, ShubException

from .utils import VALID_SCRAPY_CFG, AssertInvokeRaisesMixin, make_git_project


class BuildProjectEggTest(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        if shutil.which("git") is None:
            self.skipTest("git executable not found")

    def _egg_names(self, egg, tmpdir):
        try:
            with zipfile.ZipFile(egg) as z:
                return z.namelist()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_build_egg_excludes_gitignored_files(self):
        with self.runner.isolated_filesystem():
            make_git_project()
            # A module of the project package, which an unfiltered build
            # would include
            with Path("project", "ignored.py").open("w") as f:
                f.write("SECRET = 1\n")
            names = self._egg_names(*build_egg.build_project_egg())
        assert not any("ignored" in n for n in names)

    def test_build_egg_includes_uncommitted_tracked_changes(self):
        # A gitignore-filtered build should still deploy whatever is
        # currently on disk for tracked files, not just the last commit.
        with self.runner.isolated_filesystem():
            make_git_project()
            with Path("project", "__init__.py").open("w") as f:
                f.write("MARKER = 1\n")
            egg, tmpdir = build_egg.build_project_egg()
            try:
                with zipfile.ZipFile(egg) as z:
                    member = next(n for n in z.namelist() if n.endswith("__init__.py"))
                    content = z.read(member)
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
        assert b"MARKER = 1" in content

    def test_build_egg_includes_new_untracked_non_ignored_file(self):
        with self.runner.isolated_filesystem():
            make_git_project()
            with Path("project", "extra.py").open("w") as f:
                f.write("EXTRA = 1\n")
            names = self._egg_names(*build_egg.build_project_egg())
        assert any("extra" in n for n in names)

    def test_build_egg_skips_tracked_file_deleted_on_disk(self):
        # A file staged for deletion (removed from disk, but the removal not
        # yet committed) still shows up in `git ls-files --cached`; it should
        # simply be skipped rather than crash the build.
        with self.runner.isolated_filesystem():
            make_git_project()
            Path("project", "__init__.py").unlink()
            egg, tmpdir = build_egg.build_project_egg()
            shutil.rmtree(tmpdir, ignore_errors=True)
        assert egg.endswith(".egg")

    def test_build_egg_falls_back_without_git_repo(self):
        with self.runner.isolated_filesystem():
            with Path("scrapy.cfg").open("w") as f:
                f.write(VALID_SCRAPY_CFG)
            egg, tmpdir = build_egg.build_project_egg()
            shutil.rmtree(tmpdir, ignore_errors=True)
        assert egg.endswith(".egg")


class RemoveBuildDirTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="shub-test-build-dir-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_removes_dir(self):
        build_egg.remove_build_dir(self.tmpdir)
        assert not Path(self.tmpdir).exists()

    def test_keeps_dir_in_debug_mode(self):
        with mock.patch("shub.build_egg.click.echo") as mock_echo:
            build_egg.remove_build_dir(self.tmpdir, debug=True)
        assert Path(self.tmpdir).is_dir()
        mock_echo.assert_called_once_with(f"Output dir not removed: {self.tmpdir}")

    def test_no_dir_is_a_noop(self):
        with (
            mock.patch("shub.build_egg.shutil.rmtree") as mock_rmtree,
            mock.patch("shub.build_egg.click.echo") as mock_echo,
        ):
            build_egg.remove_build_dir(None)
            build_egg.remove_build_dir(None, debug=True)
        mock_rmtree.assert_not_called()
        mock_echo.assert_not_called()


class BuildEggCommandTest(AssertInvokeRaisesMixin, unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def _make_project(self):
        with Path("scrapy.cfg").open("w") as f:
            f.write(VALID_SCRAPY_CFG)
        Path("project").mkdir()
        Path("project", "__init__.py").touch()

    def _fake_egg_build(self):
        """Replace the egg build by a fast one that returns a fake egg in a
        temporary build dir. Return the patcher and the build dir."""
        tmpdir = tempfile.mkdtemp(prefix="shub-test-build-egg-")
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        egg = str(Path(tmpdir, "project-1.0-py3-none-any.egg"))
        with Path(egg).open("w") as f:
            f.write("egg content")
        patcher = mock.patch(
            "shub.build_egg.build_project_egg", return_value=(egg, tmpdir)
        )
        return patcher, tmpdir

    def test_builds_egg_at_requested_path(self):
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(build_egg.cli, ["built.egg"])
            assert 0 == result.exit_code, result.output
            assert "Writing egg to built.egg" in result.output
            with zipfile.ZipFile("built.egg") as z:
                assert "project/__init__.py" in z.namelist()

    def test_builds_egg_in_git_repo(self):
        if shutil.which("git") is None:
            self.skipTest("git executable not found")
        with self.runner.isolated_filesystem():
            make_git_project()
            with Path("project", "ignored.py").open("w") as f:
                f.write("SECRET = 1\n")
            result = self.runner.invoke(build_egg.cli, ["built.egg"])
            assert 0 == result.exit_code, result.output
            with zipfile.ZipFile("built.egg") as z:
                names = z.namelist()
        assert "project/__init__.py" in names
        assert not any("ignored" in n for n in names)

    @mock.patch("requests.sessions.Session.send")
    @mock.patch("shub.config.load_shub_config")
    @mock.patch("shub.deploy.load_shub_config")
    @mock.patch("shub.deploy.upload_cmd")
    @mock.patch("shub.deploy.make_deploy_request")
    def test_neither_uploads_nor_needs_config(
        self, mock_deploy_req, mock_upload_cmd, mock_deploy_conf, mock_conf, mock_send
    ):
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(build_egg.cli, ["built.egg"])
            assert 0 == result.exit_code, result.output
            assert Path("built.egg").is_file()
        # No upload and no request to any API...
        mock_deploy_req.assert_not_called()
        mock_upload_cmd.assert_not_called()
        mock_send.assert_not_called()
        # ... and no target, API key or scrapinghub.yml is needed
        mock_deploy_conf.assert_not_called()
        mock_conf.assert_not_called()

    def test_removes_build_dir(self):
        patcher, tmpdir = self._fake_egg_build()
        with patcher, self.runner.isolated_filesystem():
            result = self.runner.invoke(build_egg.cli, ["built.egg"])
            assert 0 == result.exit_code, result.output
            with Path("built.egg").open() as f:
                assert "egg content" == f.read()
        assert "Output dir not removed" not in result.output
        assert not Path(tmpdir).exists()

    def test_debug_keeps_build_dir(self):
        for option in ("-d", "--debug"):
            patcher, tmpdir = self._fake_egg_build()
            with patcher, self.runner.isolated_filesystem():
                result = self.runner.invoke(build_egg.cli, [option, "built.egg"])
                assert 0 == result.exit_code, result.output
                assert Path("built.egg").is_file()
            assert f"Output dir not removed: {tmpdir}" in result.output
            assert Path(tmpdir).is_dir()

    def test_unwritable_destination(self):
        patcher, tmpdir = self._fake_egg_build()
        with patcher, self.runner.isolated_filesystem():
            result = self.assertInvokeRaises(
                ShubException, build_egg.cli, ["no_such_dir/built.egg"]
            )
        assert (
            "Could not write egg to no_such_dir/built.egg" in result.exception.message
        )
        # The build dir is cleaned up even though the command failed
        assert not Path(tmpdir).exists()

    def test_directory_like_destination_reports_an_error(self):
        patcher, _tmpdir = self._fake_egg_build()
        with patcher, self.runner.isolated_filesystem():
            result = self.assertInvokeRaises(
                ShubException, build_egg.cli, ["no_such_dir/"]
            )
        assert "None" not in result.exception.message

    @unittest.skipIf(
        os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
        "permissions are not enforced",
    )
    def test_overwrites_write_only_destination(self):
        patcher, _tmpdir = self._fake_egg_build()
        with patcher, self.runner.isolated_filesystem():
            Path("wo.egg").touch()
            Path("wo.egg").chmod(0o200)
            result = self.runner.invoke(build_egg.cli, ["wo.egg"])
            assert 0 == result.exit_code, result.output

    def test_requires_a_scrapy_project(self):
        with self.runner.isolated_filesystem():
            self.assertInvokeRaises(NotFoundException, build_egg.cli, ["built.egg"])
            assert not Path("built.egg").exists()

    def test_filename_is_required(self):
        result = self.runner.invoke(build_egg.cli, [])
        assert 2 == result.exit_code
        assert "FILENAME" in result.output

    def test_filename_must_not_be_a_directory(self):
        with self.runner.isolated_filesystem():
            self._make_project()
            Path("built.egg").mkdir()
            result = self.runner.invoke(build_egg.cli, ["built.egg"])
        assert 2 == result.exit_code
        assert "is a directory" in result.output
