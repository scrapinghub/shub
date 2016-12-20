.. _quickstart:

==========
Quickstart
==========

Installation
------------

If you have ``pip`` installed on your system, you can install shub from the
Python Package Index::

    pip install shub

We also supply stand-alone binaries. You can find them in our `latest GitHub
release`_.

.. _`latest Github release`: https://github.com/scrapinghub/shub/releases/latest


Getting help
------------

To see all available commands, run::

    shub

For help on a specific command, run it with a ``--help`` flag, e.g.::

    shub schedule --help


Basic usage
-----------

Start by logging in::

    shub login

This will save your Scrapinghub API key to a file in your home directory
(``~/.scrapinghub.yml``) and is necessary for access to projects associated
with your Scrapinghub account.

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
