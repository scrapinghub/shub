import unittest
import os
from mock import Mock, patch

from click.testing import CliRunner
from shub import login

VALID_KEY = 32 * '1'

class LoginTest(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_login_writes_input_key_to_netrc_file(self):
        # given
        fake_netrc_writer = Mock()
        login.auth.write_key_netrc = fake_netrc_writer

        # when
        self._run()

        # then
        fake_netrc_writer.assert_called_with(VALID_KEY)

    def test_login_suggests_scrapy_cfg_username_as_key(self):
        scrapy_cfg_with_username = """
[deploy]
username = KEY_SUGGESTION
        """
        result = self._run(files={'scrapy.cfg': scrapy_cfg_with_username}, read_scrapy_cfg=True)
        err = 'Unexpected output: %s' % result.output
        self.assertTrue('KEY_SUGGESTION' in result.output, err)

    def test_login_suggests_shub_apikey_as_key(self):
        result = self._run(env={'SHUB_APIKEY': 'SHUB_APIKEY_VALUE'})
        err = 'Unexpected output: %s' % result.output
        self.assertTrue('SHUB_APIKEY_VALUE' in result.output, err)

    def test_login_can_handle_invalid_scrapy_cfg(self):
        result = self._run(files={'scrapy.cfg': 'invalid content'})
        self.assertEqual(0, result.exit_code, result.exception)

    def test_login_attempt_after_login_doesnt_lead_to_an_error(self):
        with self.runner.isolated_filesystem() as fs:
            # when
            self._run(fs=fs)
            result = self._run(fs=fs)

            # then
            self.assertEqual(0, result.exit_code)
            self.assertTrue('already logged in' in result.output, result.output)

    def _run(self, user_input=VALID_KEY, files=None, fs=None, env=None, read_scrapy_cfg=False):
        """Invokes the login cli on an isolated filesystem"""

        def write_local_test_files():
            for path, content in (files or {}).iteritems():
                with open(path, 'w') as f:
                    f.write(content)

        def invoke():
            return self.runner.invoke(login.cli, input=user_input, env=env)

        def run():
            write_local_test_files()
            login.auth.NETRC_FILE = os.path.join(fs, '.netrc')

            with patch.object(login, '_is_valid_apikey', return_value=True):
                if read_scrapy_cfg:
                    return invoke()

                with patch.object(login, '_read_scrapy_cfg_key', return_value=None):
                    return invoke()

        if fs:
            return run()

        with self.runner.isolated_filesystem() as fs:
            return run()
