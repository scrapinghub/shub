from shub import __version__
from shub.utils import get_latest_scrapy_stack

project = "shub"
project_copyright = "Scrapinghub"
version = __version__.rsplit(".", 1)[0]
release = __version__

# Stack that shub sets in newly generated scrapinghub.yml files, looked up at
# build time so that the docs do not need an update for each new stack.
rst_epilog = f"""
.. |latest-scrapy-stack| replace:: {get_latest_scrapy_stack()}
"""

extensions = ["sphinx_scrapy"]
exclude_patterns = ["_build"]

html_theme = "sphinx_rtd_theme"
