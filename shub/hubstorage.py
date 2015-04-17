from __future__ import absolute_import
import requests
from urlparse import urljoin
from shub.utils import is_valid_key, is_valid_jobid, is_valid_projectid

FORMATS = {
    'jl': 'application/x-jsonlines',
    'json': 'application/json',
    'xml': 'application/xml',
    'text': 'text/plain',
    'csv': 'text/csv',
}
BASE_API = 'https://storage.scrapinghub.com/'


class HubStorageQuery(object):
    '''Base class intended to be used by other classes aiming to query
    information from HubStorage'''

    rel_api_url = None
    allowed_formats = None

    @classmethod
    def get_allowed_formats(cls):
        '''Returns a dict with mime-types of all allowed
        data formats for the given command.'''
        return {
            x: y for x, y in FORMATS.iteritems()
            if x in cls.allowed_formats
        }

    def __init__(self, key=None, output=None, output_format=None):
        if key is not None and not is_valid_key(key):
            raise ValueError('Invalid value for "job_id" parameter')
        if not hasattr(self, 'rel_api_url'):
            msg = '{0} must have an attribute "rel_api_url"'.format(
                type(self).__name__)
            raise ValueError(msg)
        if not hasattr(self, 'allowed_formats'):
            self.allowed_formats = FORMATS.keys()
        self.key = key
        self.output = output
        self.output_format = output_format
        self.api_url = urljoin(BASE_API, self.rel_api_url)

    def _gen_request(self):
        '''Generates a request to be used later to download data.
        Must be implemented in all derived classes.'''
        raise NotImplementedError

    def download_and_write_data(self, chunk_size=1024):
        '''Downloads data and write into the descriptor. This method
        downloads data in bunchs, accordingly to the parameter chunk_size'''
        response = self._gen_request()
        for chunk in response.iter_content(chunk_size):
            self.output.write(chunk)


class HubStorageQueryLogs(HubStorageQuery):
    '''Class aimed to query log information from jobs on HubStorage'''

    allowed_formats = ['jl', 'json', 'xml', 'text', 'csv']
    rel_api_url = '/logs/'

    def __init__(self, key, output, output_format, job_id=None):
        super(HubStorageQueryLogs, self).__init__(key, output, output_format)
        if not is_valid_jobid(job_id):
            raise ValueError('Invalid value for "job_id" parameter')
        self.job_id = job_id

    def _gen_request(self):
        headers, params = {}, {}
        url = urljoin(self.api_url, self.job_id)
        headers['Accept'] = self.get_allowed_formats()[self.output_format]
        return requests.get(
            stream=True,
            url=url,
            headers=headers,
            params=params,
            auth=(self.key, ''))


class HubStorageQueryItems(HubStorageQuery):
    '''Class aimed to query items from jobs on HubStorage'''

    allowed_formats = ['jl', 'json', 'xml', 'csv']
    rel_api_url = '/items/'

    def __init__(self, key, output, output_format, job_id=None, csv_fields=None):
        super(HubStorageQueryItems, self).__init__(key, output, output_format)
        if not is_valid_jobid(job_id):
            raise ValueError('Invalid value for "job_id" parameter')
        self.job_id = job_id
        self.csv_fields = csv_fields

    def _gen_request(self):
        headers, params = {}, {}
        url = urljoin(self.api_url, self.job_id)
        headers['Accept'] = self.get_allowed_formats()[self.output_format]
        if self.csv_fields:
            params['fields'] = self.csv_fields.replace(' ', '')
        return requests.get(
            stream=True,
            url=url,
            headers=headers,
            params=params,
            auth=(self.key, ''))

class HubStorageQueryRequests(HubStorageQuery):
    '''Class aimed to query requests information from jobs on HubStorage'''

    allowed_formats = ['jl', 'json']
    rel_api_url = '/requests/'

    def __init__(self, key, output, output_format, job_id=None):
        super(HubStorageQueryRequests, self).__init__(key, output, output_format)
        if not is_valid_jobid(job_id):
            raise ValueError('Invalid value for "job_id" parameter')
        self.job_id = job_id

    def _gen_request(self):
        headers, params = {}, {}
        url = urljoin(self.api_url, self.job_id)
        headers['Accept'] = self.get_allowed_formats()[self.output_format]
        return requests.get(
            stream=True,
            url=url,
            headers=headers,
            params=params,
            auth=(self.key, ''))

class HubStorageQueryJobs(HubStorageQuery):
    '''Class aimed to query requests information from jobs on HubStorage'''

    allowed_formats = ['jl', 'json']
    rel_api_url = '/jobq/'

    def __init__(self, key, output, output_format, project_id=None):
        super(HubStorageQueryJobs, self).__init__(key, output, output_format)
        if not is_valid_projectid(project_id):
            raise ValueError('Invalid value for "project_id" parameter')
        self.project_id = project_id

    def _gen_request(self):
        headers, params = {}, {}
        url = urljoin(self.api_url, self.project_id) + '/list'
        headers['Accept'] = self.get_allowed_formats()[self.output_format]
        return requests.get(
            stream=True,
            url=url,
            headers=headers,
            params=params,
            auth=(self.key, ''))
