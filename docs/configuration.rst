.. _configuration:

=============
Configuration
=============

Where to configure shub
-----------------------

shub is configured via two YAML files:

* ``~/.scrapinghub.yml`` -- this file contains global configuration like
  your API key. It is automatically created in your home directory when you run
  ``shub login``.
* ``scrapinghub.yml`` -- this file contains local configuration like the
  project ID or the location of your requirements file. It is automatically
  created in your project directory when you run ``shub deploy`` for the first
  time.

All configuration options listed below can be used in both of these
configuration files.  In case they overlap, the local configuration file will
always take precedence over the global one.

Additionally, your Scrapinghub API key can be set as an environment variable::

    SHUB_APIKEY=12345

Defining target projects
------------------------

A very basic ``scrapinghub.yml``, as generated when you first run ``shub
deploy``, could look like this::

    project: 12345

This tells shub to deploy to the Scrapy Cloud project ``12345`` when you run
``shub deploy``.  Often, you will have multiple projects on Scrapy Cloud, e.g.
one for development and one for production. For these cases, you can replace
the ``project`` option with a ``projects`` dictionary::

    projects:
      default: 12345
      prod: 33333

shub will now deploy to project ``12345`` when you run ``shub deploy``, and
deploy to project ``33333`` when you run ``shub deploy prod``.

.. _configuration-options:

The configuration options
-------------------------

A deployed project contains more than your Scrapy code. Among other things, it
has a version tag, and often has additional package requirements or is bound to
a specific Scrapy version. All of these can be configured in
``scrapinghub.yml``.

Sometimes the requirements may be different for different target projects, e.g.
because you want to run your development project on Scrapy 1.3 but use Scrapy
1.0 for your production project. For these cases some options can be configured
either *globally* or *project-specific*.

A *global* configuration option serves as default for all projects. E.g., to
set ``scrapy:1.3-py3`` as default `Scrapy Cloud stack`_, use::

    projects:
      default: 12345
      prod: 33333

    stack: scrapy:1.3-py3

If you wish to use the stack *only* for project ``12345``, expand its entry in
``projects`` as follows::

    projects:
      default:
        id: 12345
        stack: scrapy:1.3-py3
      prod: 33333

The following is a list of all available configuration options:

================  ============================================  ===============
Option            Description                                   Scope
================  ============================================  ===============
``requirements``  Path to the project's requirements file, and  global only
                  to any additional eggs that should be
                  deployed to Scrapy Cloud. See
                  :ref:`deploying-dependencies`.
``stack``         `Scrapy Cloud stack`_ to use (this is the     global default
                  environment that your project will run in,    and project-\
                  e.g. the Scrapy version that will be used).   specific
``image``         Whether to use a custom Docker image on       global default
                  deploy. See :ref:`deploy-custom-image`.       and project-\
                                                                specific
``version``       Version tag to use when deploying. This can   global only
                  be an arbitrary string or one of the magic
                  keywords ``AUTO`` (default), ``GIT``, or
                  ``HG``. By default, ``shub`` will
                  auto-detect your version control system and
                  use its branch/commit ID as version.
``apikey``        API key to use for deployments. You will      global only
                  typically not have to touch this setting as
                  it will be configured inside
                  ``~/.scrapinghub.yml`` in your home
                  directory, via ``shub login``.
================  ============================================  ===============

.. _`Scrapy Cloud stack`: https://helpdesk.scrapinghub.com/support/solutions/articles/22000200402-scrapy-cloud-stacks


Example configurations
----------------------

Custom requirements file and fixed version information::

    project: 12345
    requirements:
      file: requirements_scrapinghub.txt
    version: 0.9.9

Custom Scrapy Cloud stack, requirements file and additional private
dependencies::

    project: 12345
    stack: scrapy:1.1
    requirements:
      file: requirements.txt
      eggs:
        - privatelib.egg
        - path/to/otherlib.egg

Using the latest Scrapy 1.3 stack in staging and development, but pinning the
production stack to a specific release::

    projects:
      default: 12345
      staging: 33333
      prod:
        id: 44444
        stack: scrapy:1.3-py3-20170322

    stack: scrapy:1.3-py3

Using a custom Docker image::

    projects:
      default: 12345
      prod: 33333

    image: true

Using a custom Docker image only for the development project::

    projects:
      default:
        id: 12345
        image: true
      prod: 33333

Using a custom Docker image in staging and development, but a Scrapy Cloud
stack in production::

    projects:
      default: 12345
      staging: 33333
      prod:
        id: 44444
        image: false
        stack: scrapy:1.3-py3-20170322

    image: true

Setting the API key used for deploying::

    project: 12345
    apikey: 0bbf4f0f691e0d9378ae00ca7bcf7f0c


Advanced use cases
------------------

It is possible to configure multiple API keys::

    projects:
      default: 123
      otheruser: someoneelse/123

    apikeys:
      default: 0bbf4f0f691e0d9378ae00ca7bcf7f0c
      someoneelse: a1aeecc4cd52744730b1ea6cd3e8412a

as well as different API endpoints::

    projects:
      dev: vagrant/3

    endpoints:
      vagrant: http://vagrant:3333/api/

    apikeys:
      default: 0bbf4f0f691e0d9378ae00ca7bcf7f0c
      vagrant: a1aeecc4cd52744730b1ea6cd3e8412a
