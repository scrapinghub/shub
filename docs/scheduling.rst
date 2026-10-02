.. _scheduling:

=====================================
Scheduling jobs and fetching job data
=====================================

shub allows you to schedule a spider run from the command line::

    shub schedule SPIDER

where ``SPIDER`` should match the spider's name. By default, shub will schedule
the spider in your default project (as defined in ``scrapinghub.yml``). You may
also explicitly specify the project to use::

    shub schedule project_alias_or_id/SPIDER

You can supply spider arguments and job-specific settings through the ``-a``
and ``-s`` options::

    $ shub schedule myspider -a ARG1=VALUE -a ARG2=VALUE
    Spider myspider scheduled, job ID: 12345/2/15
    Watch the log on the command line:
        shub log -f 2/15
    or print items as they are being scraped:
        shub items -f 2/15
    or watch it running in Zyte's web interface:
        https://app.zyte.com/p/12345/job/2/15

::

    $ shub schedule 33333/myspider -s LOG_LEVEL=DEBUG
    Spider myspider scheduled, job ID: 33333/2/15
    Watch the log on the command line:
        shub log -f 2/15
    or print items as they are being scraped:
        shub items -f 2/15
    or watch it running in Zyte's web interface:
        https://app.zyte.com/p/33333/job/2/15

You can also specify the amount of Scrapy Cloud units (``-u``) and the priority (``-p``)::

    $ shub schedule myspider -p 3 -u 3
    Spider myspider scheduled, job ID: 12345/2/16
    Watch the log on the command line:
        shub log -f 2/16
    or print items as they are being scraped:
        shub items -f 2/16
    or watch it running in Zyte's web interface:
        https://app.zyte.com/p/12345/job/2/16

shub provides commands to retrieve log entries, scraped items, or requests from
jobs. If the job is still running, you can provide the ``-f`` (follow) option
to receive live updates::

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


Listing jobs
============

To find a job key, e.g. to pass it to ``shub log``, list the latest jobs of a
project, or of a spider, with ``shub jobs``::

    $ shub jobs
    JOB         SPIDER    STATE               STARTED (UTC)
    12345/2/16  myspider  running             2016-01-02 16:38:35
    12345/1/14  other     finished (success)  2016-01-02 16:36:55

``shub jobs`` takes an optional argument that is resolved like the one of
``shub schedule``:

===================================  ===================================
``shub jobs``                        all spiders of the default project
``shub jobs 12345``                  all spiders of project 12345
``shub jobs production``             all spiders of the ``production`` target
``shub jobs myspider``               ``myspider`` in the default project
``shub jobs 12345/myspider``         ``myspider`` in project 12345
``shub jobs production/myspider``    ``myspider`` in the ``production`` target
===================================  ===================================

An argument made only of digits is taken as a project ID, and an argument
that is a target defined in ``scrapinghub.yml`` is taken as that target. If a
spider is named like that, specify the project as well, e.g.
``shub jobs default/123``.

Pending, running, and finished jobs are listed, newest first, up to ``--limit``
of them, 20 by default. Scrapy Cloud returns at most the latest 1000
jobs.

``--filter KEY=VALUE`` can be repeated to narrow the list down:

* ``state=pending``, ``state=running``, ``state=finished`` or
  ``state=deleted``: only jobs in that state (the default is to list pending,
  running and finished jobs)
* ``tag=TAG`` and ``no-tag=TAG``: only jobs that have, or do not have, that
  tag. Repeating one of them matches jobs fulfilling any of the repeated
  values.
* ``arg.NAME=VALUE``: only jobs that were run with that spider argument.

Scrapy Cloud does not support filtering by spider argument, so ``arg.*``
filters are applied by shub to the latest 1000 jobs, and ``--limit`` is
applied to what remains. The other filters are applied by Scrapy Cloud.

``--orderby FIELD`` sorts the listed jobs by ``scheduled``, ``started``,
``finished``, ``elapsed``, ``errors``, or ``spider``; append ``:asc`` to sort
in ascending order (the default is descending, i.e. newest or largest first).
Scrapy Cloud cannot sort jobs, so shub sorts only the jobs it retrieved, i.e.
the latest ``--limit`` jobs. Jobs that lack the field (e.g. a job that has not
finished has no ``finished`` time) are listed last.
