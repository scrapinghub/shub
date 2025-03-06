.. _deploying:

===================================
Deploying projects and dependencies
===================================

Deploying projects
------------------

To deploy a Scrapy project to Scrapy Cloud, navigate into the project's folder
and run::

    shub deploy [TARGET]

where ``[TARGET]`` is either a project name defined in ``scrapinghub.yml`` or a
numerical Scrapinghub project ID. If you have configured a default target in
your ``scrapinghub.yml``, you can leave out the parameter completely::

    $ shub deploy
    Packing version 3af023e-master
    Deploying to Scrapy Cloud project "12345"
    {"status": "ok", "project": 12345, "version": "3af023e-master", "spiders": 1}
    Run your spiders at: https://app.zyte.com/p/12345/

You can also deploy your project from a Python egg, or build one without
deploying::

    $ shub deploy --egg egg_name --version 1.0.0
    Using egg: egg_name
    Deploying to Scrapy Cloud project "12345"
    {"status": "ok", "project": 12345, "version": "1.0.0", "spiders": 1}
    Run your spiders at: https://app.zyte.com/p/12345/

::

    $ shub deploy --build-egg egg_name
    Writing egg to egg_name


.. _deploying-dependencies:

Deploying dependencies
----------------------

Sometimes your project will depend on third party libraries that are not
available on Scrapy Cloud. You can easily upload these by specifying a
`requirements file`_::

    # project_directory/scrapinghub.yml

    projects:
      default: 12345
      prod: 33333

    requirements:
      file: requirements.txt

Note that this requirements file is an *extension* of the `Scrapy Cloud
stack`_, and therefore should not contain packages that are already part of the
stack, such as ``scrapy``.

In case you use `pipenv`_ you may also specify a ``Pipfile``::

    # project_directory/scrapinghub.yml

    projects:
      default: 12345
      prod: 33333

    requirements:
      file: Pipfile

In this case the ``Pipfile`` must be locked and ``pipenv`` available in the 
environment.

.. note::

    To install pipenv tool, use ``pip install pipenv`` or check `its documentation
    <https://pipenv.readthedocs.io/>`_.

A requirements.txt file will be created out of the ``Pipfile`` so like the
requirements file above, it should not contain packages that are already part
of the stack.

If you use `Poetry`_ you can specify your ``pyproject.toml``::

    # project_directory/scrapinghub.yml

    projects:
      default: 12345
      prod: 33333

    requirements:
      file: pyproject.toml

This will use Poetry's ``export`` command to create a requirements.txt file. For
Poetry >= 2.0 this command is no longer installed by default and needs to manually
added as described in the
`plugin's documentation <https://github.com/python-poetry/poetry-plugin-export>`_.
If ``poetry.lock`` does not exist yet, it will be created during this process.

.. note::

    `Poetry`_ is a tool for dependency management and packaging in Python.

When your dependencies cannot be specified in a requirements file, e.g.
because they are not publicly available, you can supply them as Python eggs::

    # project_directory/scrapinghub.yml

    projects:
      default: 12345
      prod: 33333

    requirements:
      file: requirements.txt
      eggs:
        - privatelib.egg
        - path/to/otherlib.egg

Alternatively, if you cannot or don't want to supply Python eggs, you can also
build your own Docker image to be used on Scrapy Cloud. See
:ref:`deploy-custom-image`.

.. _requirements file: https://pip.pypa.io/en/stable/user_guide/#requirements-files

.. _pipenv: https://github.com/pypa/pipenv

.. _Poetry: https://poetry.eustace.io/

.. _choose-custom-stack:

Choosing a Scrapy Cloud stack
-----------------------------

You can specify the `Scrapy Cloud stack`_ to deploy your spider to by adding a
``stack`` entry to your configuration::

    # project_directory/scrapinghub.yml

    projects:
      default: 12345
    stack: scrapy:1.3-py3

It is also possible to define the stack per project for advanced use cases::

    # project_directory/scrapinghub.yml

    projects:
      default:
        id: 12345
        stack: scrapy:1.3-py3
      prod: 33333  # will use Scrapinghub's default stack

.. _`Scrapy Cloud stack`: https://helpdesk.scrapinghub.com/support/solutions/articles/22000200402-scrapy-cloud-stacks
