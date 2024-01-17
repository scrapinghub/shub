def to_unicode(text, encoding=None, errors='strict'):
    """Return the unicode representation of `text`.

    If `text` is already a ``unicode`` object, return it as-is.
    If `text` is a ``bytes`` object, decode it using `encoding`.

    Otherwise, raise an error.

    """
    if isinstance(text, str):
        return text
    if not isinstance(text, (bytes, bytearray)):
        raise TypeError('to_unicode must receive a bytes, str or unicode '
                        'object, got %s' % type(text).__name__)
    if encoding is None:
        encoding = 'utf-8'
    return text.decode(encoding, errors)


def to_bytes(text, encoding=None, errors='strict'):
    """Return the binary representation of `text`.

    If `text` is already a ``bytes`` object, return it as-is.
    If `text` is a ``unicode`` object, encode it using `encoding`.

    Otherwise, raise an error."""
    if isinstance(text, bytes):
        return text
    if isinstance(text, bytearray):
        return bytes(text)
    if not isinstance(text, str):
        raise TypeError('to_bytes must receive a unicode, str or bytes '
                        'object, got %s' % type(text).__name__)
    if encoding is None:
        encoding = 'utf-8'
    return text.encode(encoding, errors)


def to_native_str(text, encoding=None, errors='strict'):
    """Return ``str`` representation of `text`.

    ``str`` representation means ``bytes`` in PY2 and ``unicode`` in PY3.

    """
    return to_unicode(text, encoding, errors)
