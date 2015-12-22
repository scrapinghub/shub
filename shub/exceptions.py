from click import BadParameter, ClickException


class ShubException(ClickException):
    def __init__(self, msg=None):
        super(ShubException, self).__init__(msg or self.default_msg)


class MissingAuthException(ShubException):
    default_msg = "Not logged in. Please run 'shub login' first."


class InvalidAuthException(ShubException):
    default_msg = ("Authentication failure. Please make sure that your API key"
                   " is valid.")


class AlreadyLoggedInException(ShubException):
    exit_code = 0
    default_msg = ("You are already logged in. To change credentials, use "
                   "'shub logout' first.")


class ConfigParseException(ShubException):
    default_msg = "Unable to parse configuration."


class BadConfigException(ShubException):
    # Should be initialised with more specific message
    default_msg = "Please check your scrapinghub.yml."


class NotFoundException(ShubException):
    # Should be initialised with more specific message
    default_msg = "Not found."


class BadParameterException(BadParameter):
    # Proxy for clearer imports
    pass
