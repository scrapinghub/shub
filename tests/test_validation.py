import unittest

from shub.validation import validate_requirements_path


def get_sample_requirement(suffix):
    p = 'tests/samples/sample_with_requirements/requirements_%s.txt' % suffix
    return p


class ValidationTest(unittest.TestCase):
    def test_basic_requirements_is_ok(self):
        v = validate_requirements_path(get_sample_requirement('ok'))
        assert v.is_valid and not v.has_warnings

    def test_no_version_has_warnings(self):
        v = validate_requirements_path(get_sample_requirement('no_version'))
        assert v.is_valid and v.has_warnings

    def test_slow_has_warnings(self):
        v = validate_requirements_path(get_sample_requirement('slow'))
        assert v.is_valid and v.has_warnings

    def test_editable_is_not_valid(self):
        v = validate_requirements_path(get_sample_requirement('editable'))
        assert not v.is_valid
