import os
import shutil
import unittest
import zipfile

from click.testing import CliRunner

from shub import build_egg

from .utils import VALID_SCRAPY_CFG, make_git_project


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
