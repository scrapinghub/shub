.. BEGIN_SH_DOC - everything in this block will be copied to
   http://doc.scrapinghub.com/shub.html

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

If you have ``pip`` installed on your system, you can install ``shub`` from
the Python Package Index::

    pip install shub

We also supply stand-alone binaries. You can find them in our `latest GitHub
release`_.

.. _`latest Github release`: https://github.com/scrapinghub/shub/releases/latest


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
can deploy it to Scrapy Cloud via::

    shub deploy

On the first call, this will guide you through a wizard to save your project ID
into a YAML file named ``scrapinghub.yml``, living next to your ``scrapy.cfg``.
For advanced uses, you can even define aliases for multiple project IDs there::

    # project_directory/scrapinghub.yml
    projects:
      default: 12345
      prod: 33333

From anywhere within the project directory tree, you can now deploy via
``shub deploy`` (to project 12345) or ``shub deploy prod`` (to project 33333).

You can also directly supply the Scrapinghub project ID, e.g.::

    shub deploy 12345

Next, schedule one of your spiders to run on Scrapy Cloud::

    shub schedule myspider

(or ``shub schedule prod/myspider``). You can watch its log or the scraped
items while the spider is running by supplying the job ID::

    shub log -f 2/34
    shub items -f 2/34


Configuration
-------------

``shub`` reads its configuration from two YAML files: A global one in your home
directory (``~/.scrapinghub.yml``), and a local one (``scrapinghub.yml``). The
local one is typically specific to a Scrapy project and should live in the same
folder as ``scrapy.cfg``. However, ``shub`` will try all parent directories
until it finds a ``scrapinghub.yml``. When configurations overlap, the local
configuration file will always take precedence over the global one.

Both files have the same format::

    projects:
      default: 12345
      prod: 33333
    apikeys:  # populated manually or via shub login
      default: 0bbf4f0f691e0d9378ae00ca7bcf7f0c
    version: GIT  # Use git branch/commit as version when deploying. Other
                  # possible values are AUTO (default) or HG

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
    Run your spiders at: https://dash.scrapinghub.com/p/12345/

::

    $ shub deploy prod --version 1.0.0
    Packing version 1.0.0
    Deploying to Scrapy Cloud project "33333"
    {"status": "ok", "project": 33333, "version": "1.0.0", "spiders": 1}
    Run your spiders at: https://dash.scrapinghub.com/p/33333/

Run ``shub deploy -l`` to see a list of all available targets. You can also
deploy your project from a Python egg, or build one without deploying::

    $ shub deploy --egg egg_name --version 1.0.0
    Using egg: egg_name
    Deploying to Scrapy Cloud project "12345"
    {"status": "ok", "project": 12345, "version": "1.0.0", "spiders": 1}
    Run your spiders at: https://dash.scrapinghub.com/p/12345/

::

    $ shub deploy --build-egg egg_name
    Writing egg to egg_name


Deploying dependencies
----------------------

Sometimes your project will depend on third party libraries that are not
available on Scrapy Cloud. You can easily upload these via ``shub deploy-egg``
by supplying a repository URL::

    $ shub deploy-egg --from-url https://github.com/scrapinghub/dateparser.git
    Cloning the repository to a tmp folder...
    Building egg in: /tmp/egg-tmp-clone
    Deploying dependency to Scrapy Cloud project "12345"
    {"status": "ok", "egg": {"version": "v0.2.1-master", "name": "dateparser"}}
    Deployed eggs list at: https://dash.scrapinghub.com/p/12345/eggs

Or even a specific branch if using git::

    $ shub deploy-egg --from-url https://github.com/scrapinghub/dateparser.git --git-branch py3-port
    Cloning the repository to a tmp folder...
    py3-port branch was checked out
    Building egg in: /tmp/egg-tmp-clone
    Deploying dependency to Scrapy Cloud project "12345"
    {"status": "ok", "egg": {"version": "v0.1.0-30-g48841f2-py3-port", "name": "dateparser"}}
    Deployed eggs list at: https://dash.scrapinghub.com/p/12345/eggs

Or a package on PyPI::

    $ shub deploy-egg --from-pypi loginform
    Fetching loginform from pypi
    Collecting loginform
      Downloading loginform-1.0.tar.gz
      Saved /tmp/shub/loginform-1.0.tar.gz
    Successfully downloaded loginform
    Package fetched successfully
    Uncompressing: loginform-1.0.tar.gz
    Building egg in: /tmp/shub/loginform-1.0
    Deploying dependency to Scrapy Cloud project "12345"
    {"status": "ok", "egg": {"version": "loginform-1.0", "name": "loginform"}}
    Deployed eggs list at: https://dash.scrapinghub.com/p/12345/eggs

For projects that use Scrapy Cloud 2.0, instead of uploading eggs of your requirements, you
can specify a requirements file to be used::

    # project_directory/scrapinghub.yml

    projects:
      default: 12345
      prod: 33333

    requirements_file: deploy_reqs.txt

Note that this requirements file is an *extension* of the Scrapy Cloud stack, and
therefore should not contain packages that are already part of the stack, such
as ``scrapy``.

You can specify the Scrapy Cloud stack to be used by extending the ``projects`` section
of your configuration::

    # project_directory/scrapinghub.yml

    projects:
      default:
        id: 12345
        stack: scrapinghub-stack-portia
      prod: 33333  # will use the original stack


Scheduling jobs and fetching job data
-------------------------------------

``shub`` allows you to schedule a spider run from the command line::

    shub schedule SPIDER

where ``SPIDER`` should match the spider's name. By default, shub will schedule
the spider in your default project (as defined in ``scrapinghub.yml``). You may
also explicitly specify the project to use::

    shub schedule prod/SPIDER

You can supply spider arguments and job-specific settings through the ``-a``
and ``-s`` options::

    $ shub schedule myspider -a ARG1=VALUE -a ARG2=VALUE
    Spider myspider scheduled, job ID: 12345/2/15
    Watch the log on the command line:
        shub log -f 2/15
    or print items as they are being scraped:
        shub items -f 2/15
    or watch it running in Scrapinghub's web interface:
        https://dash.scrapinghub.com/p/12345/job/2/15

::

    $ shub schedule 33333/myspider -s LOG_LEVEL=DEBUG
    Spider myspider scheduled, job ID: 33333/2/15
    Watch the log on the command line:
        shub log -f 2/15
    or print items as they are being scraped:
        shub items -f 2/15
    or watch it running in Scrapinghub's web interface:
        https://dash.scrapinghub.com/p/33333/job/2/15

``shub`` provides commands to retrieve log entries, scraped items, or requests
from jobs. If the job is still running, you can provide the ``-f`` (follow)
option to receive live updates::

    $ shub log -f 2/15
    2016-01-02 16:38:35 INFO Log opened.
    2016-01-02 16:38:35 INFO [scrapy.log] Scrapy 1.0.3.post6+g2d688cd started
    ...
    # shub will keep updating the log until the job finishes or you hit CTRL+C

::

    $ shub items 2/15
    {"name": "Example product", description": "Example description"}
    {"name": "Another product", description": "Another description"}

::

    $ shub requests 1/1/1
    {"status": 200, "fp": "1ff11f1543809f1dbd714e3501d8f460b92a7a95", "rs": 138137, "_key": "1/1/1/0", "url": "http://blog.scrapinghub.com", "time": 1449834387621, "duration": 238, "method": "GET"}
    {"status": 200, "fp": "418a0964a93e139166dbf9b33575f10f31f17a1", "rs": 138137, "_key": "1/1/1/0", "url": "http://blog.scrapinghub.com", "time": 1449834390881, "duration": 163, "method": "GET"}

.. END_SH_DOC

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
