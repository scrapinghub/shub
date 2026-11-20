import os
import unittest
from pathlib import Path
from unittest import mock

import pytest
import yaml
from click.testing import CliRunner
from yaml import CLoader as Loader

from shub.config import Target
from shub.exceptions import ShubException
from shub.migrate_eggs import main


class MigrateEggsTest(unittest.TestCase):
    REQ_LIST = (
        "boto==2.38.0",
        "dateparser==0.3.3",
        "decorator==4.0.10",
        "dicttoxml==1.6.6",
        "httpretty==0.8.0",
        "hubstorage==0.16.1",
        "jdatetime==1.7.2",
        "six==1.9.0",
        "spur==0.3.15",
        "SQLAlchemy==1.0.5",
        "sqlitedict==1.3.0",
        "urllib3==1.11",
        "wheel==0.24.0",
        "wsgiref==0.1.2",
    )

    def run(self, *a, **kw):
        runner = CliRunner()
        with runner.isolated_filesystem():
            super().run(*a, **kw)

    def setUp(self):
        self.clickm = mock.patch("shub.migrate_eggs.click").start()
        gtc = mock.patch("shub.migrate_eggs.get_target_conf").start()
        self.requestsm = mock.patch("shub.migrate_eggs.requests").start()

        self.curr_dir = Path(__file__).resolve().parent

        with Path("./scrapinghub.yml").open("w") as f:
            f.write("")

        gtc.return_value = Target(
            project_id=123,
            endpoint="endpoint1",
            apikey="apikey1",
            stack="",
            image="",
            requirements_file="",
            version="",
            eggs=[],
        )

        self.addCleanup(mock.patch.stopall)

    def walksorted(self):
        return [(sorted(dirs), sorted(files)) for _, dirs, files in os.walk(".")]

    def _assert_requirements_content(self):
        with Path("./requirements.txt").open() as f:
            content = f.read()
            assert "DISABLE_DASH_EGGS" in content
            requirements = [line for line in content.split("\n") if "==" in line]
            assert requirements == list(self.REQ_LIST)

    def test_full(self):
        migrate_zip = self.curr_dir / "samples/migrate-eggs.zip"
        with migrate_zip.open("rb") as f:
            self.requestsm.get().content = f.read()

        main("default")
        self.clickm.confirm.assert_called_with(
            "Eggs will be stored in ./eggs, are you sure ? ", abort=True
        )

        files = self.walksorted()

        assert files[0] == (["eggs"], ["requirements.txt", "scrapinghub.yml"])
        assert files[1] == ([], ["1.egg", "2.egg", "3.egg"])

        with Path("./scrapinghub.yml").open() as f:
            abc = yaml.load(f, Loader=Loader)
            eggs = abc["requirements"].pop("eggs")
            eggs = [e.replace("\\", "/") for e in eggs]
            assert eggs == ["./eggs/1.egg", "./eggs/2.egg", "./eggs/3.egg"]
            assert abc == {"requirements": {"file": "./requirements.txt"}}

        self._assert_requirements_content()

        for i in ("1", "2", "3"):
            with Path(f"./eggs/{i}.egg").open() as f:
                assert f.read().strip() == i

    def test_no_eggs(self):
        file_ = "samples/migrate-eggs-no-eggs.zip"
        migrate_zip = self.curr_dir / file_
        with migrate_zip.open("rb") as f:
            self.requestsm.get().content = f.read()

        main("default")
        assert not self.clickm.confirm.called

        files = self.walksorted()
        assert files == [([], ["requirements.txt", "scrapinghub.yml"])]

        with Path("./scrapinghub.yml").open() as f:
            abc = yaml.load(f, Loader=Loader)
            assert abc == {"requirements": {"file": "./requirements.txt"}}

        self._assert_requirements_content()

    def test_override_reqs_file(self):
        file_ = "samples/migrate-eggs-no-eggs.zip"
        migrate_zip = self.curr_dir / file_
        with migrate_zip.open("rb") as f:
            self.requestsm.get().content = f.read()
        with Path("./requirements.txt").open("w") as f:
            f.write("smth==1.2.3")

        self.clickm.confirm.return_value = False
        main("default")
        self.clickm.confirm.assert_called_with(
            "requirements.txt already exists, are you sure to override it ?"
        )

        files = self.walksorted()
        assert files == [([], ["requirements.txt", "scrapinghub.yml"])]

        with Path("./scrapinghub.yml").open() as f:
            assert f.read() == ""

        with Path("./requirements.txt").open() as f:
            content = f.read()
            assert content == "smth==1.2.3"

        self.clickm.reset_mock()
        self.clickm.confirm.return_value = True
        main("default")

        self.clickm.confirm.assert_called_with(
            "requirements.txt already exists, are you sure to override it ?"
        )

        files = self.walksorted()
        assert files == [([], ["requirements.txt", "scrapinghub.yml"])]

        with Path("./scrapinghub.yml").open() as f:
            abc = yaml.load(f, Loader=Loader)
            assert abc == {"requirements": {"file": "./requirements.txt"}}

        self._assert_requirements_content()

    def _migrate_in_project_dir(self, scrapinghub_yml=""):
        """Run the migration in a subdirectory, with ``../victim`` outside of
        the project."""
        migrate_zip = self.curr_dir / "samples/migrate-eggs.zip"
        with migrate_zip.open("rb") as f:
            self.requestsm.get().content = f.read()
        Path("project").mkdir()
        os.chdir("project")
        Path("scrapinghub.yml").write_text(scrapinghub_yml)
        victim = Path("..", "victim")
        return victim

    @unittest.skipIf(os.name == "nt", "creating symbolic links needs privileges")
    def test_does_not_write_eggs_through_a_symlinked_eggs_dir(self):
        victim = self._migrate_in_project_dir()
        victim.mkdir()
        Path("eggs").symlink_to(victim.absolute())
        with pytest.raises(ShubException):
            main("default")
        assert not list(victim.iterdir())

    @unittest.skipIf(os.name == "nt", "creating symbolic links needs privileges")
    def test_does_not_write_an_egg_through_a_symlink(self):
        victim = self._migrate_in_project_dir()
        Path("eggs").mkdir()
        Path("eggs", "1.egg").symlink_to(victim.absolute())
        with pytest.raises(ShubException):
            main("default")
        assert not victim.exists()

    def test_does_not_write_requirements_outside_the_project(self):
        victim = self._migrate_in_project_dir("requirements_file: ../victim\n")
        with pytest.raises(ShubException):
            main("default")
        assert not victim.exists()

    @unittest.skipIf(os.name == "nt", "creating symbolic links needs privileges")
    def test_does_not_write_requirements_through_a_symlink(self):
        victim = self._migrate_in_project_dir()
        Path("requirements.txt").symlink_to(victim.absolute())
        with pytest.raises(ShubException):
            main("default")
        assert not victim.exists()

    @unittest.skipIf(os.name == "nt", "creating symbolic links needs privileges")
    def test_does_not_write_scrapinghub_yml_through_a_symlink(self):
        victim = self._migrate_in_project_dir()
        Path("scrapinghub.yml").unlink()
        victim.write_text("")
        Path("scrapinghub.yml").symlink_to(victim.absolute())
        with pytest.raises(ShubException):
            main("default")
        assert victim.read_text() == ""
