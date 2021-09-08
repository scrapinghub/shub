#!/usr/bin/env python
"""
A helper wrapper over start-crawl to run a custom image locally.

The wrapper is used in `shub image run` command as an entrypoint
to create a FIFO file inside a Docker container, enforce using it
to communicate with crawl process and start the crawl process.

The initial version handles and prints only LOG entries to mimic
Scrapy behavior when running locally, however it could be easily
extended in the future.

Reading about SH custom image contract should bring you more context
https://shub.readthedocs.io/en/stable/custom-images-contract.html.

FIFO based communication protocol is described well in
https://doc.zyte.com/scrapy-cloud-write-entrypoint.html

TODO As a custom image isn't necessarily based on Python, the wrapper
should be rewritten in the future with something more basic and
lightweight, to get rid of dependence on Python.
"""

from __future__ import print_function

import os
import sys
import json
import logging
import datetime
from multiprocessing import Process
from distutils.spawn import find_executable


def _consume_from_fifo(fifo_path):
    """Start reading/printing entries from FIFO."""
    with open(fifo_path) as fifo:
        while True:
            line = fifo.readline()
            # returns an empty string only in the end of the file
            if not line:
                return
            entry_type, entry_raw = line[:3], line[4:]
            _print_fifo_entry(entry_type, json.loads(entry_raw))


def _print_fifo_entry(message_type, message):
    """Print only specific entries."""
    if message_type == 'LOG':
        timestamp = _millis_to_str(message['time'])
        loglevel = logging.getLevelName(message['level'])
        # mimic Scrapy logging format as much as possible
        print('{} {} {}'.format(timestamp, loglevel, message['message']))


def _millis_to_str(millis):
    """Convert a datatime in ms to a formatted string."""
    datetime_ts = datetime.datetime.fromtimestamp(millis / 1000.0)
    return datetime_ts.strftime('%Y-%m-%d %H:%M:%S')


def main():
    """Main wrapper entrypoint."""
    # create a named pipe for communication
    fifo_path = os.environ.get('SHUB_FIFO_PATH')
    os.mkfifo(fifo_path)
    # create and start a consumer process to read from the fifo:
    # non-daemon to allow it to finish reading from pipe before exit.
    Process(target=_consume_from_fifo, args=[fifo_path]).start()
    # replace current process with original start-crawl
    os.execv(find_executable('start-crawl'), sys.argv)


if __name__ == '__main__':
    sys.exit(main())
