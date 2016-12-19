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
    or watch it running in Scrapinghub's web interface:
        https://app.scrapinghub.com/p/12345/job/2/15

::

    $ shub schedule 33333/myspider -s LOG_LEVEL=DEBUG
    Spider myspider scheduled, job ID: 33333/2/15
    Watch the log on the command line:
        shub log -f 2/15
    or print items as they are being scraped:
        shub items -f 2/15
    or watch it running in Scrapinghub's web interface:
        https://app.scrapinghub.com/p/33333/job/2/15

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
