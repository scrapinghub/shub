.. _custom-images-contract:

======================
Custom Images contract
======================

A contract is a set of requirements that any crawler custom Docker image have to comply with to be able to run on Scrapy Cloud.

Scrapy crawler Docker images are already supported via the :ref:`scrapinghub-entrypoint-scrapy <sh-entrypoint-scrapy>` contract implementation. If you want to run crawlers built using other framework/language than Scrapy/Python, you have to make sure your image follows the contract statements listed below.


Contract statements
-------------------

1. Docker image should be able to run via ``start-crawl`` command without arguments.

.. code-block:: bash

    docker run myscrapyimage start-crawl

2. Docker image should be able to return a spiders list via ``list-spiders`` command without arguments.

.. code-block:: bash

   docker run myscrapyimage list-spiders

3. Crawler should be able to get all needed params using :ref:`system environment variables <environment-variables>`.


.. _environment-variables:

Environment variables
---------------------

SHUB_JOBKEY
^^^^^^^^^^^

Job key in format ``PROJECT_ID/SPIDER_ID/JOB_ID``.

**Example**:

.. code-block:: javascript

    123/45/67


SHUB_JOB_DATA
^^^^^^^^^^^^^

Job arguments, in json format.

**Example**:

.. code-block:: javascript

    {"key": "1111112/2/2", "project": 1111112, "version": "version1",
    "spider": "spider-name", "spider_type": "auto", "tags": [],
    "priority": 2, "scheduled_by": "user", "started_by": "admin",
    "pending_time": 1460374516193, "running_time": 1460374557448, ... }

SHUB_SETTINGS
^^^^^^^^^^^^^

Job settings (i.e. organization / project / spider / job settings), in json format.

There are several layers of settings, and they all serve to different needs.

The settings may contain the following sections (dict keys):

- ``organization_settings``
- ``project_settings``
- ``spider_settings``
- ``job_settings``
- ``enabled_addons``

Organization / project / spider / job settings define appropriate levels of same settings but with different priorities. Enabled addons define Scrapinghub addons specific settings and may have an extended structure.

All the settings should replicate Dash API project ``/settings/get.json`` endpoint response (except ``job_settings`` if exists):

.. code-block:: bash

    http -a APIKEY: http://dash.scrapinghub.com/api/settings/get.json project==PROJECTID

.. note:: All environment variables starting from ``SHUB_`` are reserved for Scrapinghub internal use and shouldn’t be used with any other purposes (they will be dropped/replaced on a job start).


.. _sh-entrypoint-scrapy:

Scrapy entrypoint
-----------------

A base support wrapper written in Python implementing Custom Images contract to run Scrapy-based python crawlers and scripts on Scrapy Cloud.

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
