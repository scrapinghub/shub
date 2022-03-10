# -*- coding: utf-8 -*-
import os.path
import tempfile
from unittest import mock

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import pytest
from click.testing import CliRunner

from shub.image.run import cli, _json_dumps, WRAPPER_IMAGE_PATH
from shub.image.run.wrapper import _consume_from_fifo, _millis_to_str
from shub.image.utils import make_temp_directory


def _format_job_data(spider='spider', auth='<auth>', **kwargs):
    data = {'key': '1/2/3', 'spider': spider, 'auth': auth}
    data.update(kwargs)
    return _json_dumps(data)


@pytest.mark.usefixtures('project_dir')
def test_cli(docker_client_mock):
    docker_client_mock.create_host_config.return_value = {'host': 'config'}
    docker_client_mock.create_container.return_value = 'contID'
    docker_client_mock.logs.return_value = ['some', 'logs']
    # wrap make_temp_directory to validate its call args
    tmp_dir_fun = 'shub.image.utils.make_temp_directory'
    with mock.patch(tmp_dir_fun, wraps=make_temp_directory) as tmp_dir_mock:
        result = CliRunner().invoke(cli, ["dev/spider"])
    assert result.exit_code == 0, result.stdout
    assert tmp_dir_mock.call_args[1] == {
        'prefix': 'shub-image-run-', 'cleanup': True
    }
    docker_client_mock.start.assert_called_with('contID')
    docker_client_mock.logs.assert_called_with('contID', stream=True)
    docker_client_mock.remove_container.assert_called_with('contID', force=True)
    # validate create_container args
    docker_client_mock.create_container.assert_called_once()
    call_args = docker_client_mock.create_container.call_args[1]
    assert call_args['command'] == [WRAPPER_IMAGE_PATH]
    # validate environment
    call_env = call_args['environment']
    fifo_path = call_env.pop('SHUB_FIFO_PATH')
    assert fifo_path.endswith('scrapinghub.fifo')
    job_data = _format_job_data(spider_args={})
    expected_env = {
        'SHUB_JOBKEY': '1/2/3',
        'SHUB_SPIDER': 'spider',
        'SHUB_JOB_DATA': job_data,
        'SHUB_JOB_ENV': '{}',
        'SHUB_SETTINGS': '{"job_settings":{}}',
        'PYTHONUNBUFFERED': 1,
    }
    assert call_env == expected_env
    # validate other configuration parts
    assert call_args['host_config'] == {'host': 'config'}
    assert call_args['image'] == 'registry.io/user/project:1.0'
    assert call_args['volumes'] == [os.path.dirname(fifo_path)]


@pytest.mark.usefixtures('project_dir')
def test_cli_with_args(docker_client_mock):
    docker_client_mock.logs.return_value = []
    result = CliRunner().invoke(cli, (
        'dev/spider -a arg0= -a arg1=val1 --argument arg2=val2 '
        '-s SET1=VAL1 --set SET2=VAL2 '
        '-e ENV1=ENVVAL1 --environment ENV2=ENVVAL2 '
        '-a meta={"auth":"custom"}'.split(' ')
    ))
    assert result.exit_code == 0, result.stdout
    call_args = docker_client_mock.create_container.call_args[1]
    call_env = call_args['environment']
    expected_settings = {"job_settings": {"SET1": "VAL1", "SET2": "VAL2"}}
    assert call_env['SHUB_SETTINGS'] == _json_dumps(expected_settings)
    expected_env = {"ENV1": "ENVVAL1", "ENV2": "ENVVAL2"}
    assert call_env['SHUB_JOB_ENV'] == _json_dumps(expected_env)
    expected_jobdata = {"arg0": "", "arg1": "val1", "arg2": "val2"}
    assert call_env['SHUB_JOB_DATA'] == _format_job_data(
        spider_args=expected_jobdata, auth='custom'
    )


@pytest.mark.usefixtures('project_dir')
def test_cli_with_version(docker_client_mock):
    docker_client_mock.logs.return_value = []
    result = CliRunner().invoke(cli, ['dev/spider', '-V', 'custom'])
    assert result.exit_code == 0, result.stdout
    call_args = docker_client_mock.create_container.call_args[1]
    assert call_args['image'] == 'registry.io/user/project:custom'


@pytest.mark.usefixtures('project_dir')
def test_cli_with_script(docker_client_mock):
    docker_client_mock.logs.return_value = []
    script_args = "--flag1 --flag2=0 val1 val2"
    result = CliRunner().invoke(cli, [
        'dev/py:testargs.py', '-a', 'cmd_args="%s"' % script_args
    ])
    assert result.exit_code == 0, result.stdout
    call_args = docker_client_mock.create_container.call_args[1]
    call_env = call_args['environment']
    assert call_env['SHUB_JOB_DATA'] == _format_job_data(
        spider='py:testargs.py',
        job_cmd=["py:testargs.py", script_args],
    )


# Separate section for wrapper tests.

FIFO_TEST_TS = 1485269941065
FIFO_TEST_DATA = """\
LOG {"time": %(ts)d, "level": 20, "message": "Some message"}
ITM {"key": "value", "should-be": "ignored"}
LOG {"time": %(ts)d, "level": 30, "message": "Other message"}\
""" % {'ts': FIFO_TEST_TS}


@mock.patch('sys.stdout', new_callable=StringIO)
def test_consume_from_fifo(mock_stdout):
    try:
        # XXX work-around to use NamedTemporaryFile on Windows
        # https://github.com/appveyor/ci/issues/2547
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
            filename = temp.name
            temp.write(FIFO_TEST_DATA)
            temp.seek(0)
            _consume_from_fifo(filename)
    finally:
        os.remove(filename)
    local_datetime_string = _millis_to_str(FIFO_TEST_TS)
    assert mock_stdout.getvalue() == (
        '{date} INFO Some message\n'
        '{date} WARNING Other message\n'.format(date=local_datetime_string)
    )
