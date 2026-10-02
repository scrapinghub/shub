import json
import unittest
from unittest import mock

import requests
from click.testing import CliRunner
from scrapinghub import ScrapinghubAPIError
from scrapinghub.client.exceptions import NotFound

from shub import config, jobs
from shub.exceptions import RemoteErrorException

from .utils import AssertInvokeRaisesMixin, mock_conf

JOBS = [
    {'key': '1/2/15', 'spider': 'beta', 'state': 'running',
     'running_time': 1451752715000, 'pending_time': 1451752700000,
     'items': 500, 'errors': 3, 'spider_args': {'a': '1', 'b': 'x'}},
    # Like Scrapy Cloud, leave out counters that are 0 (here, errors)
    {'key': '1/1/14', 'spider': 'alpha', 'state': 'finished',
     'close_reason': 'cancelled', 'running_time': 1451752615000,
     'pending_time': 1451752600000, 'finished_time': 1451752640000,
     'items': 9000, 'spider_args': {'a': '2'}},
    {'key': '1/1/13', 'spider': 'alpha', 'state': 'pending',
     'pending_time': 1451752500000, 'spider_args': {'a': '2'}},
]


def iter_jobs(count=None, meta=None, **params):
    """Return JOBS like project.jobs.iter() does: at most count of them and,
    with meta, only the requested fields and a few default ones."""
    summaries = JOBS
    if meta:
        fields = {'key', 'state', 'elapsed', 'ts'} | set(meta)
        summaries = [{k: v for k, v in job.items() if k in fields}
                     for job in summaries]
    return iter(summaries[:count])


class JobsTest(AssertInvokeRaisesMixin, unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.conf = mock_conf(self)
        patcher = mock.patch('shub.jobs.get_scrapinghub_client_from_config')
        self.mock_client = patcher.start()
        self.addCleanup(patcher.stop)
        self.project = self.mock_client.return_value.get_project.return_value
        self.project.jobs.iter.side_effect = iter_jobs

    def invoke(self, *args):
        return self.runner.invoke(jobs.cli, args)

    def iter_kwargs(self):
        self.assertEqual(1, self.project.jobs.iter.call_count)
        return self.project.jobs.iter.call_args[1]

    def test_no_argument_lists_default_project(self):
        result = self.invoke()
        self.assertEqual(0, result.exit_code, result.output)
        self.mock_client.return_value.get_project.assert_called_with(1)
        self.assertEqual(
            {'state': ['pending', 'running', 'finished'], 'count': 20},
            self.iter_kwargs())
        self.project.spiders.get.assert_not_called()

    def test_output(self):
        lines = self.invoke().output.splitlines()
        self.assertEqual(4, len(lines))
        self.assertTrue(lines[0].startswith('JOB'))
        self.assertEqual(
            ['1/2/15', 'beta', 'running', '2016-01-02', '16:38:35'],
            lines[1].split())
        self.assertEqual(
            ['1/1/14', 'alpha', 'finished', '(cancelled)', '2016-01-02',
             '16:36:55'], lines[2].split())
        # Not started yet
        self.assertEqual(['1/1/13', 'alpha', 'pending', '-'], lines[3].split())

    def test_normal_close_reason_is_not_repeated(self):
        self.project.jobs.iter.side_effect = lambda **kw: iter([
            {'key': '1/1/1', 'spider': 'alpha', 'state': 'finished',
             'close_reason': 'finished', 'running_time': 1451752715000},
        ])
        lines = self.invoke().output.splitlines()
        self.assertEqual(['1/1/1', 'alpha', 'finished', '2016-01-02',
                          '16:38:35'], lines[1].split())

    def test_loads_the_configuration_once(self):
        for args in ((), ('myspider',), ('prod',), ('prod/myspider',)):
            config.load_shub_config.reset_mock()
            self.invoke(*args)
            self.assertEqual(1, config.load_shub_config.call_count, args)

    def test_project_id(self):
        result = self.invoke('12345')
        self.assertEqual(0, result.exit_code, result.output)
        self.mock_client.return_value.get_project.assert_called_with(12345)
        self.assertNotIn('spider', self.iter_kwargs())

    def test_target(self):
        self.invoke('prod')
        self.mock_client.return_value.get_project.assert_called_with(2)
        self.assertNotIn('spider', self.iter_kwargs())

    def test_spider_in_default_project(self):
        self.invoke('myspider')
        self.mock_client.return_value.get_project.assert_called_with(1)
        self.project.spiders.get.assert_called_with('myspider')
        self.assertEqual('myspider', self.iter_kwargs()['spider'])

    def test_project_id_and_spider(self):
        self.invoke('12345/myspider')
        self.mock_client.return_value.get_project.assert_called_with(12345)
        self.assertEqual('myspider', self.iter_kwargs()['spider'])

    def test_target_and_spider(self):
        self.invoke('prod/myspider')
        self.mock_client.return_value.get_project.assert_called_with(2)
        self.assertEqual('myspider', self.iter_kwargs()['spider'])

    def test_target_with_empty_spider_means_whole_project(self):
        self.invoke('prod/')
        self.mock_client.return_value.get_project.assert_called_with(2)
        self.assertNotIn('spider', self.iter_kwargs())

    def test_numeric_spider_name_needs_a_project(self):
        self.invoke('default/123')
        self.assertEqual('123', self.iter_kwargs()['spider'])

    def test_limit(self):
        self.invoke('--limit', '5')
        self.assertEqual(5, self.iter_kwargs()['count'])

    def test_limit_must_be_positive(self):
        self.assertEqual(2, self.invoke('--limit', '0').exit_code)

    def test_filters_reach_the_api(self):
        self.invoke('--filter', 'state=running', '--filter', 'state=pending',
                    '--filter', 'tag=a', '--filter', 'tag=b',
                    '--filter', 'no-tag=c')
        kwargs = self.iter_kwargs()
        self.assertEqual(['running', 'pending'], kwargs['state'])
        self.assertEqual(['a', 'b'], kwargs['has_tag'])
        self.assertEqual(['c'], kwargs['lacks_tag'])
        self.assertEqual(20, kwargs['count'])

    def test_spider_args_filter_is_applied_client_side(self):
        result = self.invoke('--filter', 'arg.a=2')
        self.assertEqual(['1/1/14', '1/1/13'], self.keys(result))
        kwargs = self.iter_kwargs()
        # The limit cannot be applied by the server before filtering
        self.assertEqual(1000, kwargs['count'])
        self.assertIn('spider_args', kwargs['meta'])

    def test_spider_args_filter_requests_all_shown_fields(self):
        lines = self.invoke('--filter', 'arg.a=2').output.splitlines()
        self.assertEqual(
            ['1/1/14', 'alpha', 'finished', '(cancelled)', '2016-01-02',
             '16:36:55'], lines[1].split())
        self.assertEqual(['1/1/13', 'alpha', 'pending', '-'], lines[2].split())

    def test_several_spider_args_must_all_match(self):
        result = self.invoke('--filter', 'arg.a=1', '--filter', 'arg.b=x')
        self.assertEqual(['1/2/15'], self.keys(result))
        result = self.invoke('--filter', 'arg.a=1', '--filter', 'arg.b=y')
        self.assertEqual("No jobs found.\n", result.output)

    def test_repeated_spider_arg_must_all_match(self):
        for first, second in (('arg.a=1', 'arg.a=2'), ('arg.a=2', 'arg.a=1')):
            result = self.invoke('--filter', first, '--filter', second)
            self.assertEqual("No jobs found.\n", result.output)

    def test_limit_applies_after_spider_args_filter(self):
        # The latest job does not match, the 2 others do
        result = self.invoke('--filter', 'arg.a=2', '--limit', '1')
        self.assertEqual(['1/1/14'], self.keys(result))

    def test_invalid_filters(self):
        for bad in ('state', 'state=', 'state=bogus', 'color=red', 'arg.=1'):
            result = self.invoke('--filter', bad)
            self.assertEqual(64, result.exit_code, bad)
            self.assertIn('--filter', result.output)
        self.project.jobs.iter.assert_not_called()

    def keys(self, result):
        return [line.split()[0] for line in result.output.splitlines()[1:]]

    def test_orderby(self):
        for orderby, expected in [
            ('items', ['1/1/14', '1/2/15', '1/1/13']),
            ('items:desc', ['1/1/14', '1/2/15', '1/1/13']),
            ('items:asc', ['1/1/13', '1/2/15', '1/1/14']),
            ('errors', ['1/2/15', '1/1/14', '1/1/13']),
            ('spider:asc', ['1/1/14', '1/1/13', '1/2/15']),
            ('spider:desc', ['1/2/15', '1/1/14', '1/1/13']),
            ('scheduled:asc', ['1/1/13', '1/1/14', '1/2/15']),
            ('started', ['1/2/15', '1/1/14', '1/1/13']),
        ]:
            self.assertEqual(expected, self.keys(self.invoke('--orderby', orderby)), orderby)

    def test_orderby_puts_jobs_lacking_the_field_last(self):
        # Only one job is finished
        self.assertEqual(['1/1/14', '1/2/15', '1/1/13'],
                         self.keys(self.invoke('--orderby', 'finished:desc')))
        self.assertEqual(['1/1/14', '1/2/15', '1/1/13'],
                         self.keys(self.invoke('--orderby', 'finished:asc')))

    def test_orderby_counts_missing_counters_as_0(self):
        self.assertEqual(['1/1/14', '1/1/13', '1/2/15'],
                         self.keys(self.invoke('--orderby', 'errors:asc')))

    def test_null_fields(self):
        # e.g. requested through meta for --filter arg.NAME=VALUE, but unset
        self.project.jobs.iter.side_effect = lambda **kw: iter([
            {'key': '1/1/2', 'spider': None, 'state': None, 'items': None,
             'running_time': None},
            {'key': '1/1/1', 'spider': 'alpha', 'state': 'running',
             'items': 3, 'running_time': 1451752715000},
        ])
        result = self.invoke('--orderby', 'items')
        self.assertEqual(0, result.exit_code, result.output)
        lines = result.output.splitlines()
        self.assertEqual('1/1/1', lines[1].split()[0])
        self.assertEqual(['1/1/2', '-', '-', '-'], lines[2].split())

    def test_orderby_is_not_sent_to_the_api(self):
        self.invoke('--orderby', 'items')
        self.assertNotIn('orderby', self.iter_kwargs())

    def test_invalid_orderby(self):
        # elapsed is the time since the job's last update, not its duration
        for bad in ('bogus', 'started:up', 'key', 'elapsed'):
            result = self.invoke('--orderby', bad)
            self.assertEqual(64, result.exit_code, bad)
            self.assertIn('--orderby', result.output)

    def test_no_jobs(self):
        self.project.jobs.iter.side_effect = lambda **kw: iter([])
        result = self.invoke()
        self.assertEqual(0, result.exit_code)
        self.assertEqual("No jobs found.\n", result.output)

    def test_unknown_spider(self):
        self.project.spiders.get.side_effect = NotFound("Spider x doesn't exist.")
        result = self.assertInvokeRaises(RemoteErrorException, jobs.cli, ['x'])
        self.assertIn("doesn't exist", result.exception.message)
        self.project.jobs.iter.assert_not_called()

    def test_api_error(self):
        self.project.jobs.iter.side_effect = ScrapinghubAPIError('Unauthorized')
        self.assertInvokeRaises(RemoteErrorException, jobs.cli, [])

    def test_api_error_while_streaming(self):
        def failing(**kw):
            yield JOBS[0]
            raise ScrapinghubAPIError('Server error')
        self.project.jobs.iter.side_effect = failing
        self.assertInvokeRaises(RemoteErrorException, jobs.cli, [])

    def test_network_error(self):
        self.project.jobs.iter.side_effect = requests.ConnectionError('down')
        self.assertInvokeRaises(RemoteErrorException, jobs.cli, [])

    def test_invalid_response(self):
        # e.g. an HTML page from a proxy
        self.project.jobs.iter.side_effect = json.JSONDecodeError(
            'Expecting value', '<html>', 0)
        self.assertInvokeRaises(RemoteErrorException, jobs.cli, [])


class UnknownTargetTest(unittest.TestCase):

    def test_unknown_target(self):
        mock_conf(self)
        result = CliRunner().invoke(jobs.cli, ['nonexistent/spider'])
        self.assertNotEqual(0, result.exit_code)
        self.assertIn('nonexistent', result.output)
