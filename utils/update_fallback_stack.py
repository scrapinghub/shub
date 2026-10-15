# /// script
# requires-python = ">=3.10"
# dependencies = ["shub"]
#
# [tool.uv.sources]
# shub = { path = "../", editable = true }
# ///
"""Set FALLBACK_SCRAPY_STACK to the latest Scrapy Cloud stack.

bump-my-version runs this before each release commit (see pyproject.toml), so
that each release of shub falls back to the latest stack available when it was
released.
"""
import re
from pathlib import Path

from shub.utils import _fetch_latest_scrapy_stack

UTILS_PATH = Path(__file__).parents[1] / 'shub' / 'utils.py'
FALLBACK_SCRAPY_STACK = re.compile(r"^FALLBACK_SCRAPY_STACK = '.*'$",
                                   re.MULTILINE)


def main():
    stack = _fetch_latest_scrapy_stack()
    code, count = FALLBACK_SCRAPY_STACK.subn(
        f"FALLBACK_SCRAPY_STACK = '{stack}'",
        UTILS_PATH.read_text(encoding='utf-8'),
    )
    if count != 1:
        raise RuntimeError(f"Found {count} definitions of "
                           f"FALLBACK_SCRAPY_STACK in {UTILS_PATH}, "
                           f"expected 1")
    UTILS_PATH.write_text(code, encoding='utf-8')
    print(f"Set FALLBACK_SCRAPY_STACK to {stack!r}")


if __name__ == '__main__':
    main()
