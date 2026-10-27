import json
import unittest
from unittest import mock

import requests
from click.testing import CliRunner

from shub import tracks
from shub.exceptions import RemoteErrorException

from .utils import mock_conf

ENDPOINT = "https://app.zyte.com/api/"


def make_response(status=200, data=None, reason="OK"):
    response = requests.Response()
    response.status_code = status
    response.reason = reason
    response._content = json.dumps(data).encode()
    return response


class TracksTest(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        mock_conf(self)
        patcher = mock.patch("shub.tracks.requests.request", autospec=True)
        self.request = patcher.start()
        self.addCleanup(patcher.stop)

    def invoke(self, *args):
        return self.runner.invoke(tracks.cli, args)

    def test_list(self):
        self.request.side_effect = [
            make_response(
                data={
                    "next": f"{ENDPOINT}projects/1/tracks?page=2",
                    "results": [{"name": "a", "version": "v1"}],
                }
            ),
            make_response(
                data={"next": None, "results": [{"name": "longer", "version": "v2"}]}
            ),
        ]
        result = self.invoke("list")
        assert result.output == "a       v1\nlonger  v2\n"
        calls = [
            (call.args, call.kwargs["params"]) for call in self.request.call_args_list
        ]
        assert calls == [
            (("GET", f"{ENDPOINT}projects/1/tracks"), {}),
            (("GET", f"{ENDPOINT}projects/1/tracks?page=2"), None),
        ]
        assert self.request.call_args.kwargs["auth"] == (32 * "1", "")

    def test_list_archived_of_target(self):
        self.request.return_value = make_response(data={"next": None, "results": []})
        result = self.invoke("list", "prod", "--archived")
        assert result.output == "No tracks found.\n"
        assert self.request.call_args.args == ("GET", f"{ENDPOINT}projects/2/tracks")
        assert self.request.call_args.kwargs["params"] == {"archived": "true"}

    def test_archive(self):
        self.request.return_value = make_response(204)
        result = self.invoke("archive", "my-track")
        assert result.output == "Track my-track archived.\n"
        assert self.request.call_args.args == (
            "DELETE",
            f"{ENDPOINT}projects/1/tracks/my-track",
        )

    def test_restore_in_target(self):
        self.request.return_value = make_response(data={"name": "my-track"})
        result = self.invoke("restore", "vagrant/my-track")
        assert result.output == "Track my-track restored.\n"
        assert self.request.call_args.args == (
            "PATCH",
            "https://vagrant_ep/api/projects/3/tracks/my-track",
        )
        assert self.request.call_args.kwargs["json"] == {"archived": False}
        assert self.request.call_args.kwargs["auth"] == (32 * "2", "")

    def test_error(self):
        self.request.return_value = make_response(
            404, {"detail": "Not found."}, "Not Found"
        )
        result = self.invoke("archive", "missing")
        assert result.exit_code == RemoteErrorException.exit_code
        assert "404 Not Found: Not found." in result.output
