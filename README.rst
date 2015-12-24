Scrapinghub command line client
===============================

``shub`` is the Scrapinghub command line client. It allows you to deploy
projects or dependencies, schedule spiders, and retrieve scraped data or logs
without leaving the command line.


Requirements
------------

* Python 2.7


Installation
------------

Install with::

    pip install shub


Usage
-----

To see all available commands, run::

    shub

For help on a specific command, run it with a ``--help`` flag, e.g.::

    shub schedule --help


Quickstart
----------

Start by logging in::

    shub login

This will save your Scrapinghub API key to a file in your home directory
(``~/.scrapinghub.yml``) and is necessary for access to projects associated
with your Scrapinghub account.

Next, navigate to a Scrapy project that you wish to upload to Scrapinghub. You
can deploy it to Scrapy Cloud by providing the Scrapinghub project ID, e.g.::

    shub deploy 12345

Of course, it would be cumbersome if you had to re-enter the project ID
everytime you wish to deploy. You can define a default project ID, and even
aliases for multiple project IDs in a YAML configuration file named
``scrapinghub.yml``, living next to your ``scrapy.cfg``::

    # project_directory/scrapinghub.yml
    projects:
      default: 12345
      prod: 33333

From anywhere within the project directory tree, you can now deploy via
``shub deploy`` (to project 12345) or ``shub deploy prod`` (to project 33333).

Next, schedule one of your spiders to run on Scrapy Cloud::

    shub schedule myspider

(or ``shub schedule prod/myspider``). When the job is finished, you can fetch
its log or items by supplying the job ID::

    shub log 2/34
    shub items 2/34


Advanced Configuration
----------------------

``shub`` reads its configuration from two YAML files: A global one in your home
directory (``~/.scrapinghub.yml``), and a local one (``scrapinghub.yml``). The
local one is typically specific to a Scrapy project and should live in the same
folder as ``scrapy.cfg``. However, ``shub`` will try all parent directories
until it finds a ``scrapinghub.yml``. When configurations overlap, the local
configuration file will always take precedence over the global one.

Besides projects (see above), you can configure different endpoints for project
deployments. A typical global ``~/.scrapinghub.yml`` could look like this::

    # ~/.scrapinghub.yml
    endpoints:
      vagrant: http://vagrant:3333/api/scrapyd/
    apikeys:  # populated manually or via shub login
      default: 0bbf4f0f691e0d9378ae00ca7bcf7f0c
      vagrant: a1aeecc4cd52744730b1ea6cd3e8412a

While a local project ``scrapinghub.yml`` could look like this::

    # project_directory/scrapinghub.yml
    projects:
      default: vagrant/3  # project 3 at vagrant endpoint
      prod: 12345         # project 12345 at default endpoint
    version: GIT  # Use git branch/commit as version. Other possible values are
                  # AUTO (default) or HG
