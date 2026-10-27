import warnings
from unittest import mock

import pytest

from shub import exceptions
from shub.exceptions import (
    AlreadyLoggedInException,
    BadConfigException,
    ConfigParseException,
    CustomImageTooLargeException,
    DeployRequestTooLargeException,
    InvalidAuthException,
    MissingAuthException,
    NotFoundException,
    RemoteErrorException,
    ShubDeprecationWarning,
    ShubWarning,
    SubcommandException,
    print_warning,
)


@pytest.mark.parametrize(
    ("exc_cls", "exit_code"),
    [
        (MissingAuthException, 67),
        (InvalidAuthException, 77),
        (AlreadyLoggedInException, 0),
        (ConfigParseException, 65),
        (BadConfigException, 78),
        (NotFoundException, 69),
        (SubcommandException, 65),
        (RemoteErrorException, 76),
        (DeployRequestTooLargeException, 65),
        (CustomImageTooLargeException, 65),
    ],
)
def test_shub_exception(exc_cls, exit_code):
    assert exc_cls.exit_code == exit_code
    assert exc_cls().message == exc_cls.default_msg
    assert exc_cls("custom message").message == "custom message"


@pytest.mark.parametrize("category", [ShubWarning, ShubDeprecationWarning])
def test_print_warning(category, capsys):
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        old_showwarning = warnings.showwarning
        print_warning("Something is off", category=category)
        assert warnings.showwarning is old_showwarning
    assert capsys.readouterr().err == "WARNING: Something is off\n"


def test_print_warning_unwritable_stderr():
    with (
        warnings.catch_warnings(),
        mock.patch.object(exceptions.sys, "stderr") as mock_stderr,
    ):
        warnings.simplefilter("always")
        mock_stderr.write.side_effect = OSError
        print_warning("Something is off")
    mock_stderr.write.assert_called_once_with("WARNING: Something is off\n")
