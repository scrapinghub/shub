import mock
import pytest
import requests
from click.testing import CliRunner

from shub.exceptions import RemoteErrorException
from shub.list_stacks import (
    cli, filter_tags, get_repository_tags, RELEASES_WEB_URL, TAGS_API_URL,
    STACK_REPOSITORIES)


TAGS = ['1.3', '1.3-py3', '1.3-20170421', '1.3-py3-20170421',
        '1.2-20161201-forwarder', '1.1-test', '1.1-20160726.1']


@pytest.fixture
def requests_get_mock():
    with mock.patch('shub.list_stacks.requests.get') as m:
        yield m


def test_get_tags_extracts_tags(requests_get_mock):
    repo = 'scrapinghub/stack-repo'
    requests_get_mock.return_value.json.return_value = [
        {'name': tag} for tag in TAGS]
    assert get_repository_tags(repo) == TAGS
    requests_get_mock.assert_called_once_with(TAGS_API_URL.format(repo=repo))


def _assert_repo_urls_in_str(x):
    for _, _, repo in STACK_REPOSITORIES:
        assert RELEASES_WEB_URL.format(repo=repo) in x


def test_get_tags_prints_urls_on_connection_error(requests_get_mock):
    requests_get_mock.side_effect = requests.ConnectionError(
        "ConnectionError description")
    with pytest.raises(RemoteErrorException) as e:
        get_repository_tags('some_repo')
        assert "ConnectionError description" in e.args[0]
        _assert_repo_urls_in_str(e.args[0])


def test_get_tags_prints_urls_on_http_error(requests_get_mock):
    requests_get_mock.return_value.raise_for_status.side_effect = (
        requests.HTTPError)
    requests_get_mock.return_value.json.return_value = {
        'message': 'HTTPError description'}
    with pytest.raises(RemoteErrorException) as e:
        get_repository_tags('some_repo')
        assert "HTTPError description" in e.args[0]
        _assert_repo_urls_in_str(e.args[0])


def test_filter_tags():
    assert filter_tags(TAGS) == ['1.3', '1.3-py3', '1.1-test']
    assert filter_tags(TAGS, include_regular=True) == TAGS


def test_cli_prints_tags():
    runner = CliRunner()
    with mock.patch('shub.list_stacks.get_repository_tags') as mock_tags:
        mock_tags.return_value = TAGS
        result = runner.invoke(cli)
        for desc, prefix, repo in STACK_REPOSITORIES:
            assert desc in result.output
            for tag in filter_tags(TAGS):
                assert prefix + ':' + tag in result.output
        result = runner.invoke(cli, ('--all', ))
        for desc, prefix, repo in STACK_REPOSITORIES:
            for tag in TAGS:
                assert prefix + ':' + tag in result.output
