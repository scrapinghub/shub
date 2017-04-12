"""
shub-specific exceptions.

Exit codes follow the sysexits.h convention:
https://www.freebsd.org/cgi/man.cgi?query=sysexits&sektion=3
"""

from __future__ import absolute_import

import sys
import warnings

from click import BadParameter, ClickException


class ShubException(ClickException):
    def __init__(self, msg=None):
        super(ShubException, self).__init__(msg or self.default_msg)


class MissingAuthException(ShubException):
    # EX_NOPERM would be more appropriate here but would forbid distinguishing
    # this from InvalidAuth by exit code
    exit_code = 67  # EX_NOUSER
    default_msg = "Not logged in. Please run 'shub login' first."


class InvalidAuthException(ShubException):
    exit_code = 77  # EX_NOPERM
    default_msg = ("Authentication failure. Please make sure that your API key"
                   " is valid.")


class AlreadyLoggedInException(ShubException):
    exit_code = 0
    default_msg = ("You are already logged in. To change credentials, use "
                   "'shub logout' first.")


class ConfigParseException(ShubException):
    exit_code = 65  # EX_DATAERR
    default_msg = "Unable to parse configuration."


class BadConfigException(ShubException):
    exit_code = 78  # EX_CONFIG
    # Should be initialised with more specific message
    default_msg = "Please check your scrapinghub.yml."


class NotFoundException(ShubException):
    # Should be initialised with more specific message
    exit_code = 69  # EX_UNAVAILABLE
    default_msg = "Not found."


class BadParameterException(BadParameter):
    exit_code = 64  # EX_USAGE


class SubcommandException(ShubException):
    exit_code = 65  # EX_DATAERR
    default_msg = "Error while calling subcommand."


class RemoteErrorException(ShubException):
    exit_code = 76  # EX_PROTOCOL
    # Should be initialised with more specific message
    default_msg = "Remote error."


class ShubWarning(Warning):
    """Base class for custom warnings."""


class ShubDeprecationWarning(ShubWarning):
    """Warning category for deprecated features, since the default
    DeprecationWarning is silenced on Python 2.7+
    """


def print_warning(msg, category=ShubWarning):
    """Helper to use Python warnings with custom formatter."""

    def custom_showwarning(message, *args, **kwargs):
        # ignore everything except the message
        try:
            sys.stderr.write("WARNING: " + str(message) + '\n')
        # stderr is invalid - this warning just gets lost
        except (IOError, UnicodeError):
            pass

    old_showwarning = warnings.showwarning
    try:
        warnings.showwarning = custom_showwarning
        warnings.warn(msg, category=category)
    finally:
        warnings.formatwarning = old_showwarning
