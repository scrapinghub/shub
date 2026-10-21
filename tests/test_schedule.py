import unittest
from unittest import mock

import pytest
from click.testing import CliRunner
from scrapinghub import ScrapinghubAPIError

from shub import schedule
from shub.exceptions import RemoteErrorException

from .utils import mock_conf


class ScheduleTest(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.conf = mock_conf(self)

    @mock.patch("shub.schedule.schedule_spider", autospec=True)
    def test_schedules_job_if_input_is_ok(self, mock_schedule):
        proj, endpoint, apikey = self.conf.get_target("default")
        # Default
        self.runner.invoke(schedule.cli, ["spider"])
        mock_schedule.assert_called_with(
            proj,
            endpoint,
            apikey,
            "spider",
            (),
            (),
            2,
            None,
            (),
            (),
            inherited=None,
            deploy_track=None,
        )
        # Other project
        self.runner.invoke(schedule.cli, ["123/spider"])
        mock_schedule.assert_called_with(
            123,
            endpoint,
            apikey,
            "spider",
            (),
            (),
            2,
            None,
            (),
            (),
            inherited=None,
            deploy_track=None,
        )
        # Other endpoint
        proj, endpoint, apikey = self.conf.get_target("vagrant")
        self.runner.invoke(schedule.cli, ["vagrant/spider"])
        mock_schedule.assert_called_with(
            proj,
            endpoint,
            apikey,
            "spider",
            (),
            (),
            2,
            None,
            (),
            (),
            inherited=None,
            deploy_track=None,
        )
        # Other project at other endpoint
        self.runner.invoke(schedule.cli, ["vagrant/456/spider"])
        mock_schedule.assert_called_with(
            456,
            endpoint,
            apikey,
            "spider",
            (),
            (),
            2,
            None,
            (),
            (),
            inherited=None,
            deploy_track=None,
        )

    @mock.patch("shub.schedule.ScrapinghubClient", autospec=True)
    def test_schedule_invalid_spider(self, mock_client):
        mock_proj = mock_client.return_value.get_project.return_value
        mock_proj.jobs.run.side_effect = ScrapinghubAPIError("")
        with pytest.raises(RemoteErrorException):
            schedule.schedule_spider(
                1, "https://endpoint/api/", "FAKE_API_KEY", "fake_spider"
            )

    @mock.patch("shub.schedule.ScrapinghubClient", autospec=True)
    def test_schedule_spider_calls_project_jobs_run(self, mock_client):
        mock_proj = mock_client.return_value.get_project.return_value
        schedule.schedule_spider(
            1, "https://endpoint/api/", "FAKE_API_KEY", "fake_spider"
        )
        assert mock_proj.jobs.run

    @mock.patch("shub.schedule.ScrapinghubClient", autospec=True)
    def test_forwards_args_and_settings(self, mock_client):
        mock_proj = mock_client.return_value.get_project.return_value
        self.runner.invoke(
            schedule.cli,
            [
                "testspider",
                "-s",
                "SETT=99",
                "-a",
                "ARG=val1",
                "--set",
                "SETTWITHEQUAL=10=10",
                "--argument",
                "ARGWITHEQUAL=val2=val2",
            ],
        )
        job_args = mock_proj.jobs.run.call_args[1]["job_args"]
        assert {"ARG": "val1", "ARGWITHEQUAL": "val2=val2"}.items() <= job_args.items()
        job_settings = mock_proj.jobs.run.call_args[1]["job_settings"]
        assert {"SETT": "99", "SETTWITHEQUAL": "10=10"} == job_settings

    @mock.patch("shub.schedule.get_job", autospec=True)
    @mock.patch("shub.schedule.ScrapinghubClient", autospec=True)
    def test_inherits(self, mock_client, mock_get_job):
        mock_proj = mock_client.return_value.get_project.return_value
        mock_get_job.return_value.metadata = {
            "spider_args": {"A": "1", "B": "2"},
            "job_settings": {"S": 3},
            "environment": {"E": "4"},
            "tags": ["t1", "t2"],
        }

        self.runner.invoke(
            schedule.cli,
            ["testspider", "-i", "2/15", "-a", "B=5", "-t", "t2", "-t", "t3"],
        )
        mock_get_job.assert_called_with("2/15")
        kwargs = mock_proj.jobs.run.call_args[1]
        assert kwargs["job_args"] == {"A": "1", "B": "5"}
        assert kwargs["job_settings"] == {"S": 3}
        assert kwargs["environment"] == {"E": "4"}
        assert kwargs["add_tag"] == ("t1", "t2", "t3")

        self.runner.invoke(
            schedule.cli,
            ["testspider", "-i", "2/15", "--inherit-settings", "--inherit-tags"],
        )
        kwargs = mock_proj.jobs.run.call_args[1]
        assert kwargs["job_args"] == {}
        assert kwargs["job_settings"] == {"S": 3}
        assert kwargs["environment"] == {}
        assert kwargs["add_tag"] == ("t1", "t2")

    @mock.patch("shub.schedule.get_job", autospec=True)
    @mock.patch("shub.schedule.ScrapinghubClient", autospec=True)
    def test_does_not_inherit_deploy_track_tags(self, mock_client, mock_get_job):
        mock_proj = mock_client.return_value.get_project.return_value
        mock_get_job.return_value.metadata = {
            "tags": ["t1", "deploy_track:experiment"],
        }

        self.runner.invoke(schedule.cli, ["testspider", "-i", "2/15"])

        assert mock_proj.jobs.run.call_args[1]["add_tag"] == ("t1",)

    @mock.patch("shub.schedule.ScrapinghubClient", autospec=True)
    def test_forwards_deploy_track(self, mock_client):
        mock_proj = mock_client.return_value.get_project.return_value
        self.runner.invoke(schedule.cli, ["testspider", "--track", "experiment"])
        call_kwargs = mock_proj.jobs.run.call_args[1]
        assert call_kwargs["deploy-track"] == "experiment"

    @mock.patch("shub.schedule.ScrapinghubClient", autospec=True)
    def test_sends_no_deploy_track_by_default(self, mock_client):
        mock_proj = mock_client.return_value.get_project.return_value
        self.runner.invoke(schedule.cli, ["testspider"])
        assert "deploy-track" not in mock_proj.jobs.run.call_args[1]

    @mock.patch("shub.schedule.schedule_spider", autospec=True)
    def test_inherit_flag_requires_inherit_from(self, mock_schedule):
        result = self.runner.invoke(schedule.cli, ["testspider", "--inherit-args"])
        assert result.exit_code == 64
        assert "--inherit-from" in result.output
        mock_schedule.assert_not_called()

    @mock.patch("shub.schedule.ScrapinghubClient", autospec=True)
    def test_forwards_tags(self, mock_client):
        mock_proj = mock_client.return_value.get_project.return_value
        self.runner.invoke(
            schedule.cli, ["testspider", "-t", "tag1", "-t", "tag2", "--tag", "tag3"]
        )
        call_kwargs = mock_proj.jobs.run.call_args[1]
        assert call_kwargs["add_tag"] == ("tag1", "tag2", "tag3")

    @mock.patch("shub.schedule.ScrapinghubClient", autospec=True)
    def test_forwards_priority(self, mock_client):
        mock_proj = mock_client.return_value.get_project.return_value
        # short option name
        self.runner.invoke(schedule.cli, ["testspider", "-p", "3"])
        call_kwargs = mock_proj.jobs.run.call_args[1]
        assert call_kwargs["priority"] == 3
        # long option name
        self.runner.invoke(schedule.cli, ["testspider", "--priority", "1"])
        call_kwargs = mock_proj.jobs.run.call_args[1]
        assert call_kwargs["priority"] == 1

    @mock.patch("shub.schedule.ScrapinghubClient", autospec=True)
    def test_forwards_units(self, mock_client):
        mock_proj = mock_client.return_value.get_project.return_value
        # no units specified
        self.runner.invoke(schedule.cli, ["testspider"])
        call_kwargs = mock_proj.jobs.run.call_args[1]
        assert call_kwargs["units"] is None
        # short option name
        self.runner.invoke(schedule.cli, ["testspider", "-u", "4"])
        call_kwargs = mock_proj.jobs.run.call_args[1]
        assert call_kwargs["units"] == 4
        # long option name
        self.runner.invoke(schedule.cli, ["testspider", "--units", "3"])
        call_kwargs = mock_proj.jobs.run.call_args[1]
        assert call_kwargs["units"] == 3

    @mock.patch("shub.schedule.ScrapinghubClient", autospec=True)
    def test_forwards_environment(self, mock_client):
        mock_proj = mock_client.return_value.get_project.return_value
        self.runner.invoke(
            schedule.cli,
            ["testspider", "-e", "VAR1=VAL1", "--environment", "VAR2=VAL2"],
        )
        call_kwargs = mock_proj.jobs.run.call_args[1]
        assert {"VAR1": "VAL1", "VAR2": "VAL2"}.items() <= call_kwargs[
            "environment"
        ].items()


@mock.patch("shub.schedule.ScrapinghubClient", autospec=True)
def test_complete_spider(mock_client):
    mock_proj = mock_client.return_value.get_project.return_value
    mock_proj.spiders.list.return_value = [{"id": "hotels"}, {"id": "news"}]
    with mock.patch("shub.schedule.get_target_conf", autospec=True) as conf:
        assert schedule._complete_spider(None, None, "ho") == ["hotels"]
        conf.assert_called_with("default")
        assert schedule._complete_spider(None, None, "prod/") == [
            "prod/hotels",
            "prod/news",
        ]
        conf.assert_called_with("prod")
        conf.side_effect = Exception
        assert schedule._complete_spider(None, None, "") == []
