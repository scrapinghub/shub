.. _custom-images-contract:

======================
Custom Images contract
======================

This is a set of requirements that any custom `Docker`_ image has to comply with
to be able to run on Scrapy Cloud.

Scrapy crawler Docker images are already supported via
the :ref:`scrapinghub-entrypoint-scrapy <sh-entrypoint-scrapy>` contract implementation.
If you want to run crawlers built using other framework/language than Scrapy/Python,
you have to make sure your image follows the contract statements listed below.

.. _Docker: https://docs.docker.com/

Contract statements
-------------------

1. Docker image should be able to run via ``start-crawl`` command without arguments.
   ``start-crawl`` should be :ref:`executable and located on the search path <scripts-example>`.

.. code-block:: bash

    docker run myscrapyimage start-crawl

2. Docker image should be able to return a spiders list via ``list-spiders`` command without arguments.
   ``list-spiders`` should be :ref:`executable and located on the search path <scripts-example>`.

.. code-block:: bash

   docker run myscrapyimage list-spiders

3. Crawler should be able to get all needed params using :ref:`system environment variables <environment-variables>`.

.. _scripts-example:

.. note::

    The simplest way to place scripts on the search path is to create a
    symbolic link to the script located in the directory present in the `PATH`_
    environment variable. Here's an example `Dockerfile`_:

    .. code-block:: dockerfile

       FROM python:3
       RUN mkdir -p /spiders
       WORKDIR /spiders
       ADD . /spiders
       # Create a symbolic link in /usr/sbin because it's present in the PATH
       RUN ln -s /spiders/start-crawl /usr/sbin/start-crawl
       RUN ln -s /spiders/list-spiders /usr/sbin/list-spiders
       # Make scripts executable
       RUN chmod +x /spiders/start-crawl /spiders/list-spiders

.. _PATH: http://pubs.opengroup.org/onlinepubs/7908799/xbd/envvar.html#tag_002_003
.. _Dockerfile: https://docs.docker.com/engine/reference/builder/

.. _environment-variables:

Environment variables
---------------------

SHUB_SPIDER
^^^^^^^^^^^

Spider name.

**Example**:

.. code-block:: javascript

    test-spider


SHUB_JOBKEY
^^^^^^^^^^^

Job key in format ``PROJECT_ID/SPIDER_ID/JOB_ID``.

**Example**:

.. code-block:: javascript

    123/45/67


SHUB_JOB_DATA
^^^^^^^^^^^^^

Job arguments, in JSON format.


**Example**:

.. code-block:: javascript

    {"key": "1111112/2/2", "project": 1111112, "version": "version1",
    "spider": "spider-name", "spider_type": "auto", "tags": ["tagA", "tagB"],
    "priority": 2, "scheduled_by": "user", "started_by": "john",
    "pending_time": 1460374516193, "running_time": 1460374557448, ... }


Some useful fields
__________________

============ ======================================================== =================================
Field        Description                                              Example
============ ======================================================== =================================
key          Job key in format ``PROJECT_ID/SPIDER_ID/JOB_ID``        ``"1111112/2/2"``
project      Integer project ID                                       ``1111112``
spider       String spider name                                       ``"spider-name"``
spider_args  Spider args dictionary                                   ``{"arg1":"val1"}``
version      String project version used to run the job               ``"version1"``
units        Amount of units used by the job                          ``1``
priority     Job priority value                                       ``2``
tags         List of string tags for the job                          ``["tagA", "tagB"]``
state        Job current state name                                   ``"running"``
pending_time UNIX timestamp when the job was added, in milliseconds   ``1460374516193``
running_time UNIX timestamp when the job was started, in milliseconds ``1460374557448``
auth         Job authentication string to access job data             ``""eyJ0e***.eyJhd***.9H5Oq***"``
scheduled_by Username who scheduled the job                           ``"john"``
============ ======================================================== =================================

If you specified some custom metadata with ``meta`` field when scheduling the job, the data will also be in the dictionary.

.. warning::

    There could be some other fields but it's for internal use only and not a part of the contract.


SHUB_SETTINGS
^^^^^^^^^^^^^

Job settings (i.e. organization / project / spider / job settings), in JSON format.

There are several layers of settings, and they all serve to different needs.

The settings may contain the following sections (dict keys):

- ``organization_settings``
- ``project_settings``
- ``spider_settings``
- ``job_settings``
- ``enabled_addons``

Organization / project / spider / job settings define appropriate levels of same settings
but with different priorities. Enabled addons define Scrapinghub addons specific settings
and may have an extended structure.

All the settings should replicate Dash API project ``/settings/get.json`` endpoint response
(except ``job_settings`` if exists):

.. code-block:: bash

    http -a APIKEY: http://dash.scrapinghub.com/api/settings/get.json project==PROJECTID

.. note::

    All environment variables starting from ``SHUB_`` are reserved for Scrapinghub internal use
    and shouldn’t be used with any other purposes (they will be dropped/replaced on a job start).


.. _sh-entrypoint-scrapy:

Scrapy entrypoint
-----------------

A base support wrapper written in Python implementing Custom Images contract to run
Scrapy-based python crawlers and scripts on Scrapy Cloud.

Main functions of this wrapper are the following:

- providing ``start-crawl`` entrypoint
- providing ``list-spiders`` entrypoint (starting from ``0.7.0`` version)
- translating system environment variables to Scrapy ``crawl`` / ``list`` commands

In fact, there are a lot of different features:

- parsing job data from environment
- processing job args and settings
- running a job with Scrapy
- collecting stats
- advanced logging & error handling
- transparent integration with Scrapinghub storage
- custom scripts support

**scrapinghub-entrypoint-scrapy** package is available on:

- `PyPI <https://pypi.python.org/pypi/scrapinghub-entrypoint-scrapy>`_
- `Github <https://github.com/scrapinghub/scrapinghub-entrypoint-scrapy/>`_
