from shub import __version__

project = "shub"
project_copyright = "Scrapinghub"
version = __version__.rsplit(".", 1)[0]
release = __version__

extensions = ["sphinx_scrapy"]
exclude_patterns = ["_build"]

html_theme = "sphinx_rtd_theme"
