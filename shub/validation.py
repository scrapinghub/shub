"""
Provide validation tools for user input,
right now deals only with requirements.txt content.

This implements the guidelines from:
https://support.scrapinghub.com/topics/1970-deploying-dependencies-to-your-scrapinghub-project/
"""
from collections import namedtuple

import requirements

ValidationTuple = namedtuple('ValidationTuple', ['line', 'name', 'message'])
ValidationResult = namedtuple('ValidationResult',
                              ['is_valid', 'has_warnings', 'errors', 'warnings'])
ValidationAttempt = namedtuple('ValidationAttempt',
                               ['should_stop', 'should_ask_to_continue'])


def _is_gitgit(req):
    """
    Return whether the requirement specifier is a git+git scheme (not recommended).
    """
    from urlparse import urlparse

    uri = req.uri

    if uri is None:
        return False

    p = urlparse(uri)
    return p.scheme.lower() == 'git+git'


def _has_pinned_version(req):
    """
    Return whether the requirement specifier is a pinned version or a URI spec.
    """
    try:
        return (req.uri is not None) or (req.specifier and req.specs[0][0] == '==')
    except IndexError:
        # Specs didn't contain ==
        return False


def validate_requirements(reqstr):
    """
    Validate a requirements file, given it's content.
    Return a ValidationResult
    """
    reqs = requirements.parse(reqstr)

    errors, warnings = [], []

    for i, req in enumerate(reqs):
        if req.editable:
            errors.append(ValidationTuple(i + 1, req.name, 'is editable'))
        elif _is_gitgit(req):
            warnings.append(
                ValidationTuple(i + 1, req.name, 'points to a git repository, use http scheme'))
        elif not _has_pinned_version(req):
            warnings.append(ValidationTuple(i + 1, req.name, 'has no version specification'))

    return ValidationResult(is_valid=not errors, has_warnings=len(warnings) > 0,
                            errors=errors, warnings=warnings)


def validate_requirements_path(requirements_path):
    """
    Validate a requirements file, given it's path.
    Return a ValidationResult.
    """
    with open(requirements_path, 'r') as f:
        reqstr = f.read()

    return validate_requirements(reqstr)


def dump_result(result, dump_fct):
    """
    Call the dump_fct for every validation result string.
    """
    dump_fct('validating requirements:')
    for r in result.warnings:
        dump_fct('WARNING: %s %s (l.%s)' % (r.name, r.message, r.line))

    for r in result.errors:
        dump_fct('ERROR: %s %s (l.%s)' % (r.name, r.message, r.line))


def validate_and_dump_for_path(requirements_path, dump_fct):
    """
    Validate a requirements file, given it's path.
    Dump the errors and warning of the validation using the dump_fct.

    Returns a ValidationAttempt.
    """
    result = validate_requirements_path(requirements_path)
    dump_result(result, dump_fct)
    return ValidationAttempt(should_stop=not result.is_valid,
                             should_ask_to_continue=result.has_warnings)

