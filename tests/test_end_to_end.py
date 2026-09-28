import os
import unittest

from click.testing import CliRunner

from shub import tool


@unittest.skipUnless(os.getenv("USING_TOX"), "End to end tests only run via TOX")
class ShubEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def run_subcmd(self, subcmd):
        return self.runner.invoke(tool.cli, [subcmd]).output

    def test_usage_is_displayed_if_no_arg_is_provided(self):
        output = self.run_subcmd("")
        usage_is_displayed = output.startswith("Usage:")
        assert usage_is_displayed

    def test_deploy_egg_isnt_broken(self):
        output = self.run_subcmd("deploy-egg")
        error = f"Unexpected output: {output}"
        assert "specify target" in output, error

    def test_deploy_reqs_isnt_broken(self):
        output = self.run_subcmd("deploy-reqs")
        error = f"Unexpected output: {output}"
        assert "specify target" in output, error

    def test_deploy_isnt_broken(self):
        output = self.run_subcmd("deploy")
        error = f"Unexpected output: {output}"
        assert "Cannot find project" in output, error

    def test_fetch_eggs_isnt_broken(self):
        output = self.run_subcmd("fetch-eggs")
        error = f"Unexpected output: {output}"
        assert "specify target" in output, error
