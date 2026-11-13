import warnings

import pytest

from shub.exceptions import ShubDeprecationWarning, ShubWarning, print_warning


@pytest.mark.parametrize("category", [ShubWarning, ShubDeprecationWarning])
def test_print_warning(category, capsys):
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        old_showwarning = warnings.showwarning
        print_warning("Something is off", category=category)
        assert warnings.showwarning is old_showwarning
    assert capsys.readouterr().err == "WARNING: Something is off\n"
