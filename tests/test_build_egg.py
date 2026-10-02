import os
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock

from click.testing import CliRunner

from shub import build_egg
from shub.exceptions import NotFoundException, ShubException

from .utils import AssertInvokeRaisesMixin, VALID_SCRAPY_CFG, make_git_project


class BuildProjectEggTest(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        if shutil.which('git') is None:
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
            with open('ignored.txt', 'w') as f:
                f.write('should not be deployed')
            names = self._egg_names(*build_egg.build_project_egg())
        self.assertFalse(any('ignored' in n for n in names))

    def test_build_egg_includes_uncommitted_tracked_changes(self):
        # A gitignore-filtered build should still deploy whatever is
        # currently on disk for tracked files, not just the last commit.
        with self.runner.isolated_filesystem():
            make_git_project()
            with open(os.path.join('project', '__init__.py'), 'w') as f:
                f.write('MARKER = 1\n')
            egg, tmpdir = build_egg.build_project_egg()
            try:
                with zipfile.ZipFile(egg) as z:
                    member = next(
                        n for n in z.namelist() if n.endswith('__init__.py'))
                    content = z.read(member)
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertIn(b'MARKER = 1', content)

    def test_build_egg_includes_new_untracked_non_ignored_file(self):
        with self.runner.isolated_filesystem():
            make_git_project()
            with open(os.path.join('project', 'extra.py'), 'w') as f:
                f.write('EXTRA = 1\n')
            names = self._egg_names(*build_egg.build_project_egg())
        self.assertTrue(any('extra' in n for n in names))

    def test_build_egg_skips_tracked_file_deleted_on_disk(self):
        # A file staged for deletion (removed from disk, but the removal not
        # yet committed) still shows up in `git ls-files --cached`; it should
        # simply be skipped rather than crash the build.
        with self.runner.isolated_filesystem():
            make_git_project()
            os.remove(os.path.join('project', '__init__.py'))
            egg, tmpdir = build_egg.build_project_egg()
            shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertTrue(egg.endswith('.egg'))

    def test_build_egg_falls_back_without_git_repo(self):
        with self.runner.isolated_filesystem():
            with open('scrapy.cfg', 'w') as f:
                f.write(VALID_SCRAPY_CFG)
            egg, tmpdir = build_egg.build_project_egg()
            shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertTrue(egg.endswith('.egg'))


class RemoveBuildDirTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='shub-test-build-dir-')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_removes_dir(self):
        build_egg.remove_build_dir(self.tmpdir)
        self.assertFalse(os.path.exists(self.tmpdir))

    def test_keeps_dir_in_debug_mode(self):
        with mock.patch('shub.build_egg.click.echo') as mock_echo:
            build_egg.remove_build_dir(self.tmpdir, debug=True)
        self.assertTrue(os.path.isdir(self.tmpdir))
        mock_echo.assert_called_once_with(
            "Output dir not removed: %s" % self.tmpdir)

    def test_no_dir_is_a_noop(self):
        with mock.patch('shub.build_egg.shutil.rmtree') as mock_rmtree, \
                mock.patch('shub.build_egg.click.echo') as mock_echo:
            build_egg.remove_build_dir(None)
            build_egg.remove_build_dir(None, debug=True)
        mock_rmtree.assert_not_called()
        mock_echo.assert_not_called()


class BuildEggCommandTest(AssertInvokeRaisesMixin, unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def _make_project(self):
        with open('scrapy.cfg', 'w') as f:
            f.write(VALID_SCRAPY_CFG)
        os.mkdir('project')
        open(os.path.join('project', '__init__.py'), 'w').close()

    def _fake_egg_build(self):
        """Replace the egg build by a fast one that returns a fake egg in a
        temporary build dir. Return the patcher and the build dir."""
        tmpdir = tempfile.mkdtemp(prefix='shub-test-build-egg-')
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        egg = os.path.join(tmpdir, 'project-1.0-py3-none-any.egg')
        with open(egg, 'w') as f:
            f.write('egg content')
        patcher = mock.patch('shub.build_egg.build_project_egg',
                             return_value=(egg, tmpdir))
        return patcher, tmpdir

    def test_builds_egg_at_requested_path(self):
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(build_egg.cli, ['built.egg'])
            self.assertEqual(0, result.exit_code, result.output)
            self.assertIn('Writing egg to built.egg', result.output)
            with zipfile.ZipFile('built.egg') as z:
                self.assertIn('project/__init__.py', z.namelist())

    def test_builds_egg_in_git_repo(self):
        if shutil.which('git') is None:
            self.skipTest("git executable not found")
        with self.runner.isolated_filesystem():
            make_git_project()
            with open('ignored.txt', 'w') as f:
                f.write('should not be in the egg')
            result = self.runner.invoke(build_egg.cli, ['built.egg'])
            self.assertEqual(0, result.exit_code, result.output)
            with zipfile.ZipFile('built.egg') as z:
                names = z.namelist()
        self.assertIn('project/__init__.py', names)
        self.assertFalse(any('ignored' in n for n in names))

    @mock.patch('requests.sessions.Session.send')
    @mock.patch('shub.config.load_shub_config')
    @mock.patch('shub.deploy.load_shub_config')
    @mock.patch('shub.deploy.upload_cmd')
    @mock.patch('shub.deploy.make_deploy_request')
    def test_neither_uploads_nor_needs_config(
            self, mock_deploy_req, mock_upload_cmd, mock_deploy_conf,
            mock_conf, mock_send):
        with self.runner.isolated_filesystem():
            self._make_project()
            result = self.runner.invoke(build_egg.cli, ['built.egg'])
            self.assertEqual(0, result.exit_code, result.output)
            self.assertTrue(os.path.isfile('built.egg'))
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
            result = self.runner.invoke(build_egg.cli, ['built.egg'])
            self.assertEqual(0, result.exit_code, result.output)
            with open('built.egg') as f:
                self.assertEqual('egg content', f.read())
        self.assertNotIn('Output dir not removed', result.output)
        self.assertFalse(os.path.exists(tmpdir))

    def test_debug_keeps_build_dir(self):
        for option in ('-d', '--debug'):
            patcher, tmpdir = self._fake_egg_build()
            with patcher, self.runner.isolated_filesystem():
                result = self.runner.invoke(
                    build_egg.cli, [option, 'built.egg'])
                self.assertEqual(0, result.exit_code, result.output)
                self.assertTrue(os.path.isfile('built.egg'))
            self.assertIn('Output dir not removed: %s' % tmpdir,
                          result.output)
            self.assertTrue(os.path.isdir(tmpdir))

    def test_unwritable_destination(self):
        patcher, tmpdir = self._fake_egg_build()
        with patcher, self.runner.isolated_filesystem():
            result = self.assertInvokeRaises(
                ShubException, build_egg.cli, ['no_such_dir/built.egg'])
        self.assertIn('Could not write egg to no_such_dir/built.egg',
                      result.exception.message)
        # The build dir is cleaned up even though the command failed
        self.assertFalse(os.path.exists(tmpdir))

    def test_directory_like_destination_reports_an_error(self):
        patcher, tmpdir = self._fake_egg_build()
        with patcher, self.runner.isolated_filesystem():
            result = self.assertInvokeRaises(
                ShubException, build_egg.cli, ['no_such_dir/'])
        self.assertNotIn('None', result.exception.message)

    @unittest.skipIf(os.name == 'nt' or (hasattr(os, 'geteuid') and os.geteuid() == 0),
                     "permissions are not enforced")
    def test_overwrites_write_only_destination(self):
        patcher, tmpdir = self._fake_egg_build()
        with patcher, self.runner.isolated_filesystem():
            open('wo.egg', 'w').close()
            os.chmod('wo.egg', 0o200)
            result = self.runner.invoke(build_egg.cli, ['wo.egg'])
            self.assertEqual(0, result.exit_code, result.output)

    def test_requires_a_scrapy_project(self):
        with self.runner.isolated_filesystem():
            self.assertInvokeRaises(
                NotFoundException, build_egg.cli, ['built.egg'])
            self.assertFalse(os.path.exists('built.egg'))

    def test_filename_is_required(self):
        result = self.runner.invoke(build_egg.cli, [])
        self.assertEqual(2, result.exit_code)
        self.assertIn("FILENAME", result.output)

    def test_filename_must_not_be_a_directory(self):
        with self.runner.isolated_filesystem():
            self._make_project()
            os.mkdir('built.egg')
            result = self.runner.invoke(build_egg.cli, ['built.egg'])
        self.assertEqual(2, result.exit_code)
        self.assertIn("is a directory", result.output)
