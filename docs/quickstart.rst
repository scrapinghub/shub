.. _quickstart:

==========
Quickstart
==========

Installation
------------

If you have ``pip`` installed on your system, you can install shub from the
Python Package Index::

    pip install shub


Getting help
------------

To see all available commands, run::

    shub

For help on a specific command, run it with a ``--help`` flag, e.g.::

    shub schedule --help


Shell completion
----------------

To enable tab completion of commands, options and spider names, add the
following line to :file:`~/.bashrc`::

    eval "$(_SHUB_COMPLETE=bash_source shub)"

For other shells, see the `Click shell completion docs`_.

.. _Click shell completion docs: https://click.palletsprojects.com/en/stable/shell-completion/


.. _basic-usage:

Basic usage
-----------

Start by logging in::

    shub login

This will save your Scrapinghub API key to a file in your home directory
(``~/.scrapinghub.yml``) and is necessary for access to projects associated
with your Scrapinghub account. Alternatively, you can set your Scrapinghub
API key as an environment variable (``SHUB_APIKEY``), check :ref:`an appropriate
section <configuration-environment>` for details.

Next, navigate to a Scrapy project that you wish to upload to Scrapinghub. You
can deploy it to Scrapy Cloud via::

    shub deploy

On the first call, this will guide you through a wizard to save your project ID
into a YAML file named ``scrapinghub.yml``, living next to your ``scrapy.cfg``.
From anywhere within the project directory tree, you can now deploy via ``shub
deploy``.

Next, schedule one of your spiders to run on Scrapy Cloud::

    shub schedule myspider

You can watch its log or the scraped items while the spider is running by
supplying the job ID::

    shub log -f 2/34
    shub items -f 2/34
