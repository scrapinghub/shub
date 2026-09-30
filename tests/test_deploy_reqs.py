import tempfile
import unittest
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from shub import deploy_reqs

from .utils import mock_conf


class TestDeployReqs(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.conf = mock_conf(self)

    @unittest.skip("flaky")
    def test_can_decompress_downloaded_packages_and_call_deploy_reqs(self):
        requirements_file = self._write_tmp_requirements_file()
        with mock.patch("shub.utils.build_and_deploy_egg") as m:
            self.runner.invoke(
                deploy_reqs.cli,
                ("-r", requirements_file),
            )
            assert m.call_count == 2
            for args, _kwargs in m.call_args_list:
                project, endpoint, apikey = args
                assert project == 1
                assert "https://app.zyte.com" in endpoint
                assert apikey == self.conf.apikeys["default"]

    def _write_tmp_requirements_file(self):
        basepath = Path("tests/samples/deploy_reqs_sample_project").resolve()
        eggs = ["other-egg-0.2.1.zip", "inflect-0.2.5.tar.gz"]
        tmp_dir = tempfile.mkdtemp(prefix="shub-test-deploy-reqs")
        requirements_file = Path(tmp_dir, "requirements.txt")

        with requirements_file.open("w") as f:
            f.writelines(f"{basepath / egg}\n" for egg in eggs)

        return str(requirements_file)
