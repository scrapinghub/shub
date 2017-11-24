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
This means you have to implement your own scripts following the specification below.
You can find example projects written in other frameworks and programming languages in
the `custom-images-examples repository`_. The ``shub bootstrap`` can be used to clone
these projects.

.. _Docker: https://docs.docker.com/
.. _custom-images-examples repository: https://github.com/scrapinghub/custom-images-examples

Contract statements
-------------------

1. Docker image should be able to run via ``start-crawl`` command without arguments.
   ``start-crawl`` should be :ref:`executable and located on the search path <scripts-example>`.

.. code-block:: bash

    docker run myscrapyimage start-crawl

   Crawler will be started by unpriviledged user ``nobody`` in a writable directory ``/scrapinghub``.
   ``HOME`` environment variable will be set to ``/scrapinghub`` as well. Beware that this directory is added
   dynamically when job starts, if Docker image contains this directory - it'll be erased.

2. Docker image should be able to return its metadata via ``shub-image-info`` command without arguments.
   ``shub-image-info`` should be :ref:`executable and located on the search path <scripts-example>`.
   For now only a few fields are supported, and all of them are required:

  - ``project_type`` - a string project type, one of [``scrapy``, ``casperjs``, ``other``],
  - ``spiders`` - a list of non-empty string spider names.

.. code-block:: bash

    docker run myscrapyimage shub-image-info
    {"project_type": "casperjs", "spiders": ["spiderA", "spiderB"]}

.. note::

    ``shub-image-info`` is an extension (and a replacement) for a former ``list-spiders`` command to provide
    metadata in a structured form allowing to simplify non-Scrapy development and parametrize custom images
    in a more configurable way.

    The command could also handle optional ``--debug`` flag by returning debug information about the image
    inside of an additional ``debug`` field: a name/version of operation system, installed packages etc.
    For example, for a Python-based custom image it could be a good idea to include ``pip freeze`` call results.
    Data format of the ``debug`` field is plain text, not structured to keep it simple.

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
       RUN ln -s /spiders/shub-image-info /usr/sbin/shub-image-info
       # Make scripts executable
       RUN chmod +x /spiders/start-crawl /spiders/shub-image-info

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
job_cmd      List of string arguments for the job                     ``["--flagA", "--key1=value1"]``
spider_args  Dictionary with spider arguments                         ``{"arg1": "val1"}``
version      String project version used to run the job               ``"version1"``
deploy_id    Integer project deploy ID used to run the job            ``253``
units        Amount of units used by the job                          ``1``
priority     Job priority value                                       ``2``
tags         List of string tags for the job                          ``["tagA", "tagB"]``
state        Job current state name                                   ``"running"``
pending_time UNIX timestamp when the job was added, in milliseconds   ``1460374516193``
running_time UNIX timestamp when the job was started, in milliseconds ``1460374557448``
scheduled_by Username who scheduled the job                           ``"john"``
============ ======================================================== =================================

If you specified some custom metadata with ``meta`` field when scheduling the job, the data will also be in the dictionary.

.. warning::

    ``SHUB_JOB_DATA`` may contain other undocumented fields. They are for the platform's internal use
     and are not part of the contract, i.e. they can appear or be removed anytime.


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
