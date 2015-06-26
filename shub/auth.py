import os
import netrc

from os.path import expanduser

from click import ClickException

OS_WIN = True if os.name == 'nt' else False
NETRC_FILE = expanduser('~/_netrc') if OS_WIN else expanduser('~/.netrc')


def find_api_key():
    """
    Raises:
        ClickException: if no credentials are found
    """
    key = get_key_netrc()

    if not key:
        key = os.getenv("SHUB_APIKEY")

    if not key:
        err = 'Not logged in. Please login first with: shub login'
        raise ClickException(err)

    return key


def get_key_netrc():
    """Gets the key from the netrc file"""
    try:
        info = netrc.netrc(NETRC_FILE)
    except IOError:
        return
    try:
        key, account, password = info.authenticators("scrapinghub.com")
    except TypeError:
        return
    if key:
        return key


def write_key_netrc(key):
    descriptor = os.open(
        NETRC_FILE,
        os.O_CREAT | os.O_RDWR | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, 'a+') as out:
        line = 'machine scrapinghub.com login {0} password ""\n'.format(key)
        out.write(line)
