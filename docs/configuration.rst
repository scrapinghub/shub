.. _configuration:

=============
Configuration
=============

shub reads its configuration from two YAML files: A global one in your home
directory (``~/.scrapinghub.yml``), and a local one (``scrapinghub.yml``). The
local one is typically specific to a Scrapy project and should live in the same
folder as ``scrapy.cfg``. However, ``shub`` will try all parent directories
until it finds a ``scrapinghub.yml``. When configurations overlap, the local
configuration file will always take precedence over the global one.

Both files have the same format::

    projects:
      default: 12345
      prod: 33333

    # Populated manually or via shub login
    apikey: 0bbf4f0f691e0d9378ae00ca7bcf7f0c

    # Use git branch/commit as version when deploying. Other possible values
    # are AUTO (default) or HG
    version: GIT

``projects`` is a mapping from human-friendly names to project IDs. This allows
you to run ``shub deploy prod`` instead of ``shub deploy 33333``. ``version``
is a string to be used as project version information when deploying to Scrapy
Cloud. By default, ``shub`` will auto-detect your version control system and
use its branch/commit ID as version.

Typically, you will configure only your API keys and the version specifier in
the global ``~/.scrapinghub.yml``, and keep project configuration in the local
``project_dir/scrapinghub.yml``. However, sometimes it can be convenient to
also configure projects in the global configuration file. This allows you to
use the human-friendly project identifiers outside of the project directory.


Advanced use cases
------------------

It is possible to configure multiple API keys::

    # scrapinghub.yml
    projects:
      default: 123
      otheruser: someoneelse/123
    apikeys:
      default: 0bbf4f0f691e0d9378ae00ca7bcf7f0c
      someoneelse: a1aeecc4cd52744730b1ea6cd3e8412a

as well as different API endpoints::

    # scrapinghub.yml
    projects:
      dev: vagrant/3
    endpoints:
      vagrant: http://vagrant:3333/api/
    apikeys:
      default: 0bbf4f0f691e0d9378ae00ca7bcf7f0c
      vagrant: a1aeecc4cd52744730b1ea6cd3e8412a
