from click import ClickException


class AuthException(ClickException):
    def __init__(self):
        msg = 'Authentication failure. Make sure your API key is valid.'
        super(AuthException, self).__init__(msg)
