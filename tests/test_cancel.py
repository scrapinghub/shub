import unittest
from unittest import mock

import pytest
from click.testing import CliRunner

from shub import cancel
from shub.exceptions import BadParameterException, ShubException, SubcommandException

from .utils import AssertInvokeRaisesMixin, mock_conf


class CancelTest(AssertInvokeRaisesMixin, unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.conf = mock_conf(self)

    @mock.patch("shub.cancel.get_scrapinghub_client_from_config")
    def test_simple_cancel_call(self, mock_client):
        client = mock_client.return_value
        mock_proj = client.get_project.return_value
        mock_proj.jobs.cancel.return_value = {"count": 2}

        result = self.runner.invoke(
            cancel.cli,
            (
                "123456",
                "1/1",
                "1/2",
            ),
            input="y\n",
        )

        assert "{'count': 2}" in result.output
        assert 0 == result.exit_code
        assert mock_proj.jobs.cancel.call_count == 1
        mock_proj.jobs.cancel.assert_called_with(keys=["123456/1/1", "123456/1/2"])

    @mock.patch("shub.cancel.get_target_conf")
    @mock.patch("shub.cancel.get_scrapinghub_client_from_config")
    def test_cancel_default_project(self, mock_client, targetconf):
        client = mock_client.return_value
        mock_proj = client.get_project.return_value
        mock_proj.jobs.cancel.return_value = {"count": 2}

        targetconf.return_value = mock.Mock(project_id="123456")

        result = self.runner.invoke(
            cancel.cli,
            (
                "1/1",
                "1/2",
            ),
            input="y\n",
        )

        assert "{'count': 2}" in result.output
        assert 0 == result.exit_code
        assert mock_proj.jobs.cancel.call_count == 1
        mock_proj.jobs.cancel.assert_called_with(keys=["123456/1/1", "123456/1/2"])

    @mock.patch("shub.cancel.get_scrapinghub_client_from_config")
    def test_invalid_job_key(self, mock_client):
        self.assertInvokeRaises(
            SystemExit,
            cancel.cli,
            (
                "123456",
                "1/1",
                "1",
            ),
            input="y\n",
        )

        self.assertInvokeRaises(
            SystemExit,
            cancel.cli,
            (
                "123456",
                "1/abc",
                "1",
            ),
            input="y\n",
        )

    @mock.patch("shub.cancel.get_scrapinghub_client_from_config")
    def test_cancel_failure(self, mock_client):
        client = mock_client.return_value
        mock_proj = client.get_project.return_value
        mock_proj.jobs.cancel.side_effect = ValueError("Error msg")

        self.assertInvokeRaises(
            ShubException,
            cancel.cli,
            (
                "123456",
                "1/1",
                "1/2",
            ),
            input="y\n",
        )

    @mock.patch("shub.cancel.get_scrapinghub_client_from_config")
    def test_cancel_abort(self, mock_client):
        result = self.runner.invoke(
            cancel.cli,
            (
                "123456",
                "1/1",
                "1/2",
            ),
            input="N\n",
        )
        assert "Aborted!" in result.output

    @mock.patch("shub.cancel.get_scrapinghub_client_from_config")
    def test_cancel_force(self, mock_client):
        mock_proj = mock_client.return_value.get_project.return_value
        mock_proj.jobs.cancel.return_value = {"count": 1}

        result = self.runner.invoke(cancel.cli, ("--force", "123456", "1/1"))

        assert "Do you want to cancel" not in result.output
        assert "{'count': 1}" in result.output
        assert 0 == result.exit_code
        mock_proj.jobs.cancel.assert_called_once_with(keys=["123456/1/1"])

    def test_validate_job_key(self):
        with pytest.raises(BadParameterException):
            cancel.validate_job_key("123456", "1")

        with pytest.raises(BadParameterException):
            cancel.validate_job_key("123456", "1/abc")

        with pytest.raises(BadParameterException):
            cancel.validate_job_key("123456", "")

    @mock.patch("shub.cancel.parse_job_key", side_effect=RuntimeError("boom"))
    def test_validate_job_key_unexpected_error(self, mock_parse):
        with pytest.raises(SubcommandException, match="boom"):
            cancel.validate_job_key("123456", "1/1")
