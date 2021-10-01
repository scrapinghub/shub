.. _deploy-custom-image:

==============================
Deploying custom Docker images
==============================

.. note::

    This feature is currently only available for paying customers.

It's possible to deploy Docker images with spiders to Scrapy Cloud. To be able to run spiders in custom `Docker`_
images it's necessary to follow the :ref:`Custom images contract <custom-images-contract>` - a set of requirements
that image should comply with to be compatible with Scrapy Cloud.

.. _Docker: https://docs.docker.com/

Deployment
==========

This section describes how to build and deploy a custom Docker image to Scrapy Cloud. For all the following steps
it's assumed that commands are executed at the root directory of your project.

1. Create Dockerfile
--------------------

The most important thing you need to be able to build and deploy Docker images is a `Dockerfile`_.
Please follow the link if you are not familiar with the concept as it's crucial to understand it
while using custom Docker images feature.

If you want to migrate an existing Scrapy project - there's a tool that may help you, please read
:ref:`this section <create-image-for-scrapy-project>`. In all other cases you're responsible for writing your own
Dockerfile. The resulting Dockerfile should produce a Docker image that follows the
:ref:`Custom images contract <custom-images-contract>` - follow the link to find an example Dockerfile.

.. _Dockerfile: https://docs.docker.com/engine/reference/builder/

2. Deploy to Scrapy Cloud
-------------------------

Once you have the Dockerfile run the :ref:`shub deploy <basic-usage>` command to build the Docker image.
If there's no :ref:`scrapinghub.yml <configuration>` configuration file at the project root
shub will start a wizard that will help to configure the project and will save the configuration file.
If you already have :ref:`scrapinghub.yml <configuration>` at the project root please ensure that
:ref:`image deploy is configured <configuration-options>` for the target project. If the target project
already exists in the configuration file but images deploy is not configured you can run
:ref:`shub image build <commands-upload>` to build the image for the first time and shub
will help you to configure the image repository.

The deploy consists of 3 stages which are described below. Normally :ref:`shub deploy <basic-usage>` will execute
all 3 stages in a single run, but in some cases in might be useful to run those stages separately,
so there are commands bundled under :ref:`shub image <commands>` that allow to execute different stages separately.

Build
^^^^^

During the build stage Docker image is built from the given Dockerfile.
This stage can be manually started with :ref:`shub image build <commands-build>` command::

    $ shub image build
    ...
    The image images.scrapinghub.com/project/XXXXXX:YYYYYY build is completed.

In the end of the command, shub will automatically run a few tests to make sure everything is alright for deployment.
You can run the test manually after the build::

    $ shub image test

.. note::

    If you want to access Docker build logs you can invoke the command in the verbose mode::

        $ shub image build -v

Push
^^^^

During the push stage the image is pushed to the repository defined in the :ref:`scrapinghub.yml <configuration>` file.
This stage can be manually started with :ref:`shub image push <commands-push>` command::

    $ shub image push
    ...
    The image images.scrapinghub.com/project/XXXXXX:YYYYYY pushed successfully.

In the example above, the image was pushed to the default Scrapinghub images registry ``images.scrapinghub.com``.

.. note::

    If you want to access Docker push logs you can invoke the command in the verbose mode::

        $ shub image push -v

Deploy
^^^^^^

During the deploy stage the image is deployed to the Scrapy Cloud.
This stage can be manually started with :ref:`shub image deploy <commands-deploy>` command::

    $ shub image deploy
    ...
    You can check deploy results later with 'shub image check --id 1'.
    Deploy results:
     {'status': 'started'}
     {'project': XXXXXX, 'status': 'ok', 'version': 'YYYYYY', 'spiders': 1}

Now you can schedule your spiders via web dashboard or shub.

.. note::

    The deploy step for a project might be slow for the first time you do it


.. _create-image-for-scrapy-project:

Create Docker image for existing Scrapy project
===============================================

If you have an existing Scrapy project and you want to run it using a custom Docker image you'll need to create
a `Dockerfile`_ for it. There's a :ref:`shub image init <commands-init>` command that creates a template
Dockerfile, which should be suitable for the majority of the Scrapy projects that run on Scrapy Cloud::

    $ shub image init

If your project has ``requirements.txt`` file you can easily add it like this::

    $ shub image init --requirements path/to/requirements.txt

.. warning::

    If you have a Scrapy project but don't want to use the generated Dockerfile or need to use a different base image
    you may want to install `scrapinghub-entrypoint-scrapy`_ Python package inside your image. It is a support layer
    that passes data from the job to Scrapinghub storage. Otherwise you will need to send data to Scrapinghub storage
    using `HTTP API`__.

.. _scrapinghub-entrypoint-scrapy: https://pypi.python.org/pypi/scrapinghub-entrypoint-scrapy
__ https://doc.scrapinghub.com/scrapy-cloud.html#storage-scrapinghub-com

.. _commands:

Commands
========

Each of the commands we used in the steps above has some options that allow you to customize their behavior.
For example, the :ref:`push <commands-push>` command allows you to pass your registry credentials
via the ``--username`` and ``--password`` options. This section lists the options available for each command.

.. _commands-build:

build
-----

This command uses the Dockerfile to build the image that's going to be deployed later.

It reads the target images from the :ref:`scrapinghub.yml <configuration>` file.
You should add a section called ``images`` on it using the following format:

.. code-block:: yaml

    projects:
      default: 11111
      prod: 22222
    # image deploy is enabled for all targets
    image: true

Or:

.. code-block:: yaml

    projects:
      default:
        id: 12345
        # image deploy is enabled only for default target
        image: true
      prod: 33333


Options for build
^^^^^^^^^^^^^^^^^

.. function:: --list-targets

List available targets and exit.

.. function:: --target <text>

Define the image for release. The ``<text>`` parameter must be one of the target names listed by ``list-targets``.

**Default value**: ``default``

.. function:: -V/--version <text>

Tag your image with ``<text>``. You'll probably not need to set this manually, because the tool automatically
sets this for you.

If you pass the ``-V``/``--version`` parameter here, you will have to pass the exact same value to any other commands
that accept this parameter (:ref:`push <commands-push>` and :ref:`deploy <commands-deploy>`).

**Default value**: identifier generated by shub.

.. function:: -S/--skip-tests

Option to skip testing image with ``shub image test`` after build.

.. function:: -v/--verbose

Increase the tool's verbosity.

.. function:: -f/--file

Use this option to pass a custom Dockerfile name (default is 'PATH/Dockerfile').

**Default value**: ``Dockerfile``

**Example:**

::

    $ shub image build --list-targets
    default
    private
    fallback
    $ shub image build --target private --version 1.0.4

.. _commands-push:

push
----

This command pushes the image built by the ``build`` command to the registry (the ``default`` or another one
specified with the ``--target option``).

Options for push
^^^^^^^^^^^^^^^^

.. function:: --list-targets

List available targets and exit.

.. function:: --target <text>

Define the image for release. The ``<text>`` parameter must be one of the target's names listed by ``list-targets``.

**Default value**: ``default``

.. function:: -V/--version <text>

Tag your image with ``<text>``. If you provided a custom version to the :ref:`build <commands-build>` command,
make sure to provide the same value here.

**Default value**: identifier generated by shub.

.. function:: --username <text>

Set the username to authenticate in the Docker registry.

**Note**: we don't store your credentials and you'll be able to use OAuth2 in the near future.

.. function:: --password <text>

Set the password to authenticate in the Docker registry.

.. function:: --email <text>

Set the email to authenticate in the Docker registry (if needed).

.. function:: --apikey <text>

Use provided apikey to authenticate in the Scrapy Cloud Docker registry.

.. function:: --insecure

Use the Docker registry in insecure mode.

.. function:: -v/--verbose

Increase the tool's verbosity.

Most of these options are related with Docker registry authentication. If you don't provide them,
shub will try to push your image using the plain HTTP ``--insecure-registry`` docker mode.

**Example:**

::

    $ shub image push --target private --version 1.0.4 \
    --username johndoe --password johndoepwd

This example authenticates the user ``johndoe`` to the registry ``your.own.registry:port`` (as defined in the
:ref:`build command example <commands-build>`).


.. _commands-deploy:

deploy
------

This command deploys your release image to Scrapy Cloud.

Options for deploy
^^^^^^^^^^^^^^^^^^

.. function:: --list-targets

List available targets and exit.

.. function:: --target <text>

Target name that defines where the image is going to be pushed to.

**Default value**: ``default``

.. function:: -V/--version <text>

The image version that you want to deploy to Scrapy Cloud. If you provided a custom version to the
:ref:`build <commands-build>` and :ref:`push <commands-push>` commands, make sure to provide the same value here.

**Default value**: identifier generated by shub

.. function:: --username <text>

Set the username to authenticate in the Docker registry.

**Note**: we don't store your credentials and you'll be able to use OAuth2 in the near future.

.. function:: --password <text>

Set the password to authenticate in the registry.

.. function:: --email <text>

Set the email to authenticate in the Docker registry (if needed).

.. function:: --apikey <text>

Use provided apikey to authenticate in the Scrapy Cloud Docker registry.

.. function:: --insecure

Use the Docker registry in insecure mode.

.. function:: --async

.. warning::

    Deploy in asynchronous mode is deprecated.

Make deploy asynchronous. When enabled, the tool will exit as soon as the deploy is started in background.
You can then check the status of your deploy task periodically via the :ref:`check <commands-check>` command.

**Default value**: ``False``


.. function:: -v/--verbose

Increase the tool's verbosity.


**Example:**

::

    $ shub image deploy --target private --version 1.0.4 \
    --username johndoe --password johndoepwd

This command will deploy the image from the ``private`` target, using user credentials passed as parameters.


.. _commands-upload:

upload
------

It is a shortcut for the build -> push -> deploy chain of commands.

**Example:**

::

    $ shub image upload --target private --version 1.0.4 \
    --username johndoe --password johndoepwd


Options for upload
^^^^^^^^^^^^^^^^^^

The ``upload`` command accepts the same parameters as the :ref:`deploy <commands-deploy>` command.


.. _commands-check:

check
-----

This command checks the status of your deployment and is useful when you do the deploy in asynchronous mode.

.. warning::

    Deploy in asynchronous mode is deprecated.

By default, the ``check`` command will return results from the last deploy.

Options for check
^^^^^^^^^^^^^^^^^

.. function:: --id <number>

The id of the deploy you want to check the status.

**Default value**: the id of the latest deploy.

**Example:**

::

    $ shub image check --id 0

This command above will check the status of the first deploy made (id 0).


.. _commands-test:

test
----

This command checks if your local setup meets the requirements for a deployment at Scrapy Cloud.
You can run it right after the :ref:`build command <commands-build>` to make sure everything is ready to go
before you push your image with the :ref:`push command <commands-push>`.

Options for test
^^^^^^^^^^^^^^^^

.. function:: --list-targets

List available targets and exit.

.. function:: --target <text>

Target name that defines an image that is going to be tested.

**Default value**: ``default``

.. function:: -V/--version <text>

The image version that you want to test. If you provided a custom version to the :ref:`deploy <commands-deploy>`,
make sure to provide the same value here.

.. function:: -v/--verbose

Increase the tool's verbosity.

list
----

This command lists spiders for your project based on the image you built and your project settings in Dash.
You can run it right after the :ref:`build command <commands-build>` to make sure that all your spiders are found.

Options for list
^^^^^^^^^^^^^^^^

.. function:: --list-targets

List available targets and exit.

.. function:: --target <text>

Target name that defines an image to get spiders list.

**Default value**: ``default``

.. function:: -V/--version <text>

The image version that you want to use to extract spiders list. If you provided a custom version to the
:ref:`deploy <commands-deploy>`, make sure to provide the same value here.

.. function:: -s/--silent-mode

Silent mode to suspend errors in a case if project isn't found for a given target in
:ref:`scrapinghub.yml <configuration>`.

.. function:: -v/--verbose

Increase the tool's verbosity.

.. _commands-init:

init
----

This command helps to migrate existing Scrapy projects to custom Docker images. It generates a ``Dockerfile``
that can be used later by the :ref:`build <commands-build>` or :ref:`upload <commands-upload>` commands.

The generated Dockerfile will likely fit your needs. But if it doesn't, it's just a matter of editing the file.

Options for init
^^^^^^^^^^^^^^^^

.. function:: --project <text>

Define the Scrapy project where the settings are going to be read from.

**Default value**: ``default`` from current folder's ``scrapy.cfg``.

.. function:: --base-image <text>

Define which `base Docker image <https://docs.docker.com/engine/reference/builder>`_ your custom image will build upon.

**Default value**: ``python:2.7``

.. function:: --requirements <path>

Set ``path`` as the Python requirements file for this project.

**Default value**: project directory ``requirements.txt``

.. function:: --add-deps <list>

Provide additional system dependencies to install in your image along with the default ones. The ``<list>`` parameter
should be a comma separated list with no spaces between dependencies.

.. function:: --list-recommended-reqs

List recommended Python requirements for a Scrapy Cloud project and exit.


**Example:**

::

    $ shub image init --base-image scrapinghub/base:12.04 \
    --requirements other/requirements-dev.txt \
    --add-deps phantomjs,tmux


Troubleshooting
===============

Image not found while deploying
-------------------------------

If you don't use default Scrapinghub repository - make sure the repository you set in your
:ref:`scrapinghub.yml <configuration>` images section exists in the registry. Consider this example:

.. code-block:: yaml

    projects:
        default: 555555
    image: johndoe/scrapy-crawler

shub will try to deploy the image to http://hub.docker.com/johndoe/scrapy-crawler, since
`hub.docker.com <http://hub.docker.com>`_ is the default Docker registry. So, to make it work,
you have to log into your account there and create the repository.

Otherwise, you are going to get an error message like this::

    Deploy results: {u'status': u'error', u'last_step': u'pulling', u'error': u"DockerCmdFailure(u'Error: image johndoe/scrapy-crawler not found',)"}


Uploading to a private repository
---------------------------------

If you are using a private repository to push your images to, make sure to pass your registry credentials to both
:ref:`push <commands-push>` and :ref:`deploy <commands-deploy>` commands::

    $ shub image push --username johndoe --password yourpass
    $ shub image deploy --username johndoe --password yourpass

Or pass it to :ref:`upload <commands-upload>` command::

    $ shub image upload --username johndoe --password yourpass


Container works locally but fails in scrapy cloud
-------------------------------------------------

Prior to running ``start-crawl`` in Scrapy Cloud, some configurations
are set to ensure we can run an isolated process.
This can lead to issues that are quite hard to debug and find the
root cause.
To aid in this process, below you willl find some steps that
are quite similar to what actually runs in scrapy cloud.

Run your container in interactive with ``bash`` (or any other
terminal that is available). Please replace the 2 occurrences of
``<SPIDER-NAME>`` with the actual spider that is to run::

    $ docker run \
    -it \
    -e SHUB_JOBKEY=123/4/5 \
    -e SHUB_JOB_DATA='{
        "_shub_worker": "kumo",
        "api_url": "https://app.zyte.com/api/",
        "auth": "<AN AUTH KEY>",
        "deploy_id": 1,
        "key": "123/4/5",
        "pending_time": 1632739881823,
        "priority": 2,
        "project": 123,
        "running_time": 1632739882059,
        "scheduled_by": "some_user",
        "spider": "<SPIDER-NAME>",
        "spider_type": "manual",
        "started_by": "jobrunner",
        "state": "running",
        "tags": [],
        "units": 1,
        "version": "1.0"
    }' \
    -e SHUB_JOB_ENV='{}' \
    -e SHUB_JOB_MEMORY_LIMIT=950 \
    -e SHUB_JOB_UID=123 \
    -e SHUB_SETTINGS='{
        "deploy_id": 1,
        "enabled_addons": [],
        "job_settings": {},
        "organization_settings": {},
        "project_settings": {},
        "spider_settings": {},
        "status": "ok",
        "version": "1.0"
    }' \
    -e SHUB_SPIDER=<SPIDER-NAME> \
    --net bridge \
    --volume=/scrapinghub \
    --rm=true \
    --name=scrapy-cloud-container \
    my-docker-image \
    /bin/bash

Connect to the container in a new terminal window
and open a named pipe to communicate through ``sh_scrapy``::

    $ docker exec -it scrapy-cloud-container /bin/bash
    $ mkfifo -m 0600 /dev/scrapinghub
    $ chown 65534:65534 /dev/scrapinghub
    $ cat /dev/scrapinghub

Go back to the first window and start the crawling process::

    $ export SHUB_FIFO_PATH=/dev/scrapinghub
    $ start-crawl

Switch back to the second window (the named pipe one)
to see the results comming out.
