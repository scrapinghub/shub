# -*- coding: utf-8 -*-
import json
import time

import mock
import pytest
from click import command
from click.testing import CliRunner
from requests import Response

from shub.image.deploy import _LoggedDeployProgress, _DeployProgress
from shub.image.deploy import _extract_scripts_from_project
from shub.image.deploy import _prepare_deploy_params
from shub.image.deploy import cli
from ..utils import clean_progress_output, format_expected_progress


@pytest.fixture
def mocked_post(monkeypatch):
    """Mock requests.post to return a HTTP 200 response with location header."""
    def fake_post(self, *args, **kwargs):
        fake_response = Response()
        fake_response.status_code = 200
        fake_response.headers = {'location': 'http://deploy/url/123'}
        return fake_response
    monkeypatch.setattr('requests.post', fake_post)


@pytest.mark.usefixtures('project_dir')
@mock.patch('requests.get')
@mock.patch('requests.post')
@mock.patch('shub.image.list.list_cmd')
def test_cli(list_mocked, post_mocked, get_mocked):
    list_mocked.return_value = {
        'project_type': 'scrapy',
        'spiders': ['a1f', 'abc', 'spi-der'],
    }
    post_req = mock.Mock()
    post_req.headers = {'location': 'https://status-url'}
    post_mocked.return_value = post_req

    result = CliRunner().invoke(cli, ["dev", "--version", "test"])
    assert result.exit_code == 0

    auth_cfg = '{"email": null, "password": " ", "username": "abcdef"}'
    post_mocked.assert_called_with(
        'https://app.scrapinghub.com/api/releases/deploy.json',
        allow_redirects=False,
        auth=('abcdef', ''),
        data={
            'project_type': 'scrapy',
            'project': 12345,
            'version': u'test',
            'pull_auth_config': auth_cfg,
            'image_url': 'registry.io/user/project:test',
            'spiders': 'a1f,abc,spi-der',
            'scripts': 'scriptA.py,scriptB.py',
        },
        timeout=300)
    get_mocked.assert_called_with('https://status-url', timeout=300)


@pytest.mark.usefixtures('project_dir')
@mock.patch('requests.get')
@mock.patch('requests.post')
@mock.patch('shub.image.list.list_cmd')
def test_cli_insecure_registry(list_mocked, post_mocked, get_mocked):
    list_mocked.return_value = {
        'project_type': 'scrapy',
        'spiders': ['a1f', 'abc', 'spi-der'],
    }
    post_req = mock.Mock()
    post_req.headers = {'location': 'https://status-url'}
    post_mocked.return_value = post_req

    result = CliRunner().invoke(cli, ["dev", "--version", "test", "--insecure"])
    assert result.exit_code == 0

    post_mocked.assert_called_with(
        'https://app.scrapinghub.com/api/releases/deploy.json',
        allow_redirects=False,
        auth=('abcdef', ''),
        data={
            'project_type': 'scrapy',
            'project': 12345,
            'version': u'test',
            'pull_insecure_registry': True,
            'image_url': 'registry.io/user/project:test',
            'spiders': 'a1f,abc,spi-der',
            'scripts': 'scriptA.py,scriptB.py',
        },
        timeout=300)
    get_mocked.assert_called_with('https://status-url', timeout=300)


# Tests for progress logic


def _format_progress_event(status, progress, total, step):
    """Helper to format progress events for mocking it with fake responses."""
    return {'status': status, 'progress': progress, 'total': total, 'last_step': step}


DEPLOY_EVENTS_SHORT_SAMPLE = [
    _format_progress_event('progress', 0,  100, 'preparing release'),
    _format_progress_event('progress', 25, 100, 'pulling image'),
    _format_progress_event('progress', 30, 100, 'pulling image'),
    {'status': 'ok', 'project': 1111112, 'version': 'test', 'spiders': 10},
]
DEPLOY_EVENTS_BASE_SAMPLE = [
    _format_progress_event('progress', 0,  100, 'preparing release'),
    _format_progress_event('progress', 25, 100, 'pulling image'),
    _format_progress_event('progress', 30, 100, 'pulling image'),
    _format_progress_event('progress', 35, 100, 'pulling image'),
    _format_progress_event('progress', 50, 100, 'pushing image'),
    _format_progress_event('progress', 55, 100, 'pushing image'),
    _format_progress_event('progress', 65, 100, 'pushing image'),
    _format_progress_event('progress', 75, 100, 'updating panel'),
    _format_progress_event('progress', 100, 100, 'updating panel'),
    {'status': 'ok', 'project': 1111112, 'version': 'test', 'spiders': 10},
]


def _load_deploy_event_result(line):
    """Helper to extract a data dictionary from parsed command output line.

    Shub tool prints the lines as python dicts, so quotes should be properly
    replaced with double quotes to extract data from json dict.
    """
    return json.loads(line.replace("'", '"'))


def _get_logged_progress_cmd(progress_cls, events):
    @command()
    def progress_cmd():
        progress = progress_cls(events)
        progress.show()
    return progress_cmd


def _yield_events_with_timeout(events, timeout):
    for event in events:
        yield event
        time.sleep(timeout)


def test_progress_verbose_logic():
    progress_cmd = _get_logged_progress_cmd(_LoggedDeployProgress,
                                            DEPLOY_EVENTS_BASE_SAMPLE)
    result = CliRunner().invoke(progress_cmd)
    assert result.exit_code == 0
    lines = result.output.split('\n')
    # test that output ends with a newline symbol
    assert lines[-1] == ''
    # test that the command succeeded
    assert _load_deploy_event_result(lines[-2]) == DEPLOY_EVENTS_BASE_SAMPLE[-1]
    # test that progress events are included in the output
    assert _load_deploy_event_result(lines[-3]) == DEPLOY_EVENTS_BASE_SAMPLE[-2]


@pytest.mark.usefixtures('monkeypatch_bar_rate')
def test_progress_bar_logic():
    events = _yield_events_with_timeout(DEPLOY_EVENTS_BASE_SAMPLE, timeout=0.1)
    progress_cmd = _get_logged_progress_cmd(_DeployProgress, events)
    result = CliRunner().invoke(progress_cmd)
    assert result.exit_code == 0
    expected = format_expected_progress(
        'Progress:   0%|          | 0/100'
        'Progress:  25%|██▌       | 25/100'
        'Progress:  30%|███       | 30/100'
        'Progress:  35%|███▌      | 35/100'
        'Progress:  50%|█████     | 50/100'
        'Progress:  55%|█████▌    | 55/100'
        'Progress:  65%|██████▌   | 65/100'
        'Progress:  75%|███████▌  | 75/100'
        'Progress: 100%|██████████| 100/100'
        'Progress: 100%|██████████| 100/100'
        'Deploy results:'
    )
    assert expected in clean_progress_output(result.output)
    lines = result.output.split('\n')
    # test that output ends with a newline symbol
    assert lines[-1] == ''
    # test that the command succeeded
    assert _load_deploy_event_result(lines[-2]) == DEPLOY_EVENTS_BASE_SAMPLE[-1]


@pytest.mark.usefixtures('monkeypatch_bar_rate')
def test_progress_bar_logic_incomplete():
    events = _yield_events_with_timeout(DEPLOY_EVENTS_SHORT_SAMPLE, timeout=0.1)
    progress_cmd = _get_logged_progress_cmd(_DeployProgress, events)
    result = CliRunner().invoke(progress_cmd)
    assert result.exit_code == 0
    expected = format_expected_progress(
        'Progress:   0%|          | 0/100'
        'Progress:  25%|██▌       | 25/100'
        'Progress:  30%|███       | 30/100'
        'Progress: 100%|██████████| 100/100'
        'Progress: 100%|██████████| 100/100'
        'Deploy results:'
    )
    assert expected in clean_progress_output(result.output)
    # test that the command succeeded
    lines = result.output.split('\n')
    # test that output ends with a newline symbol
    assert lines[-1] == ''
    # test that the command succeeded
    assert _load_deploy_event_result(lines[-2]) == DEPLOY_EVENTS_SHORT_SAMPLE[-1]


# Tests for auxiliary functions

def test_extract_scripts_from_project_empty():
    assert _extract_scripts_from_project() == []


@pytest.mark.usefixtures('project_dir')
def test_extract_scripts_from_project_fake():
    assert _extract_scripts_from_project() == ['scriptA.py', 'scriptB.py']


@pytest.mark.usefixtures('project_dir')
@mock.patch('shub.image.list.list_cmd')
def test_prepare_deploy_params(mocked):
    mocked.return_value = {
        'project_type': 'scrapy',
        'spiders': ['a1f', 'abc', 'spi-der']}
    expected = {
        'project_type': 'scrapy',
        'image_url': 'registry.io/user/project',
        'project': 123,
        'pull_insecure_registry': True,
        'scripts': 'scriptA.py,scriptB.py',
        'spiders': 'a1f,abc,spi-der',
        'version': 'test-vers',
    }
    assert _prepare_deploy_params(
        123, 'test-vers', 'registry.io/user/project',
        'endpoint', 'apikey', None, None, None) == expected


@pytest.mark.usefixtures('project_dir')
@mock.patch('shub.image.list.list_cmd')
def test_prepare_deploy_params_more_params(mocked):
    mocked.return_value = {
        'project_type': 'scrapy',
        'spiders': ['a1f', 'abc', 'spi-der'],
    }
    expected = {
        'project_type': 'scrapy',
        'image_url': 'registry.io/user/project',
        'project': 123,
        'scripts': 'scriptA.py,scriptB.py',
        'spiders': 'a1f,abc,spi-der',
        'version': 'test-vers',
        'pull_auth_config':
            '{"email": "email@mail", "password": "pass", "username": "user"}',
    }
    assert _prepare_deploy_params(
        123, 'test-vers', 'registry.io/user/project',
        'endpoint', 'apikey', 'user', 'pass', 'email@mail') == expected
