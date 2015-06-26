import unittest
import os
from mock import Mock

from click.testing import CliRunner
from shub import login


class LoginTest(unittest.TestCase):
    VALID_KEY = 32 * '1'

    def setUp(self):
        login.auth.NETRC_FILE = ''
        self.runner = CliRunner()

    def test_login_validates_api_key(self):
        result = self.runner.invoke(login.cli, input='invalid key')
        self.assertEqual(2, result.exit_code)
        self.assertTrue('Invalid key' in result.output)

    def test_login_writes_input_key_to_netrc_file(self):
        # given
        fake_netrc_writer = Mock()
        login.auth.write_key_netrc = fake_netrc_writer

        # when
        self.runner.invoke(login.cli, input=self.VALID_KEY)

        # then
        fake_netrc_writer.assert_called_with(self.VALID_KEY)

    def test_login_suggests_scrapy_cfg_username_as_key(self):
        scrapy_cfg_with_username = """
[deploy]
username = KEY_SUGGESTION
        """

        with self.runner.isolated_filesystem():
            with open('scrapy.cfg', 'w') as f:
                f.write(scrapy_cfg_with_username)

            result = self.runner.invoke(login.cli, input='123')
            err = 'Unexpected output: %s' % result.output
            self.assertTrue('KEY_SUGGESTION' in result.output, err)

    def test_login_can_handle_invalid_scrapy_cfg(self):
        # given
        invalid_scrapy_cfg = 'invalid content'

        with self.runner.isolated_filesystem() as fs:
            login.auth.NETRC_FILE = os.path.join(fs, '.netrc')

            with open('scrapy.cfg', 'w') as f:
                f.write(invalid_scrapy_cfg)

            # when
            result = self.runner.invoke(login.cli, input=self.VALID_KEY)

            # then
            self.assertEqual(0, result.exit_code, result.exception)
