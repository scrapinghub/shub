import unittest, os
from shub.logout import remove_sh_key
from tempfile import NamedTemporaryFile

class LogoutTestCase(unittest.TestCase):
    _netrc_file = None

    def setUp(self):
        self._netrc_file = self._create_tmp_netrc()

    def tearDown(self):
        self._delete_tmp_netrc(self._netrc_file)

    def test_was_key_removed_from_netrc(self):
        error_msg = remove_sh_key(self._netrc_file)
        self.assertEqual(error_msg, '')

    def _create_tmp_netrc(self):
        with NamedTemporaryFile(delete=False) as netrc:
            line = 'machine scrapinghub.com login ffffffffffffffffffffffffffffffff password ""'
            netrc.write(line)
        return netrc.name

    def _delete_tmp_netrc(self, netrc_file):
        if netrc_file:
            os.remove(netrc_file)

if __name__ == '__main__':
    unittest.main()
