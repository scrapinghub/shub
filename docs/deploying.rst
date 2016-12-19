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
    Run your spiders at: https://app.scrapinghub.com/p/12345/

::

    $ shub deploy prod --version 1.0.0
    Packing version 1.0.0
    Deploying to Scrapy Cloud project "33333"
    {"status": "ok", "project": 33333, "version": "1.0.0", "spiders": 1}
    Run your spiders at: https://app.scrapinghub.com/p/33333/

Run ``shub deploy -l`` to see a list of all available targets. You can also
deploy your project from a Python egg, or build one without deploying::

    $ shub deploy --egg egg_name --version 1.0.0
    Using egg: egg_name
    Deploying to Scrapy Cloud project "12345"
    {"status": "ok", "project": 12345, "version": "1.0.0", "spiders": 1}
    Run your spiders at: https://app.scrapinghub.com/p/12345/

::

    $ shub deploy --build-egg egg_name
    Writing egg to egg_name


Deploying dependencies
----------------------

Sometimes your project will depend on third party libraries that are not
available on Scrapy Cloud. You can easily upload these by specifying a
requirements file::

    # project_directory/scrapinghub.yml

    projects:
      default: 12345
      prod: 33333

    requirements:
      file: requirements.txt

Note that this requirements file is an *extension* of the Scrapy Cloud stack, and
therefore should not contain packages that are already part of the stack, such
as ``scrapy``.

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


Choosing a Scrapy Cloud stack
-----------------------------

You can specify the `Scrapy Cloud stack`_ to deploy your spider to by extending
the ``projects`` section of your configuration::

    # project_directory/scrapinghub.yml

    projects:
      default:
        id: 12345
        stack: scrapy:1.1-py3
      prod: 33333  # will use the original stack

.. _`Scrapy Cloud stack`: http://doc.scrapinghub.com/scrapy-cloud.html#using-stacks
