#!/usr/bin/env python
import json
import multiprocessing
import six
from threading import Thread
from argparse import ArgumentParser
from socketserver import TCPServer
from http.server import SimpleHTTPRequestHandler
from six.moves import urllib


class Handler(SimpleHTTPRequestHandler):

    def _do_any(self):
        method = self.command
        path, _, querystr = self.path.partition('?')
        query = urllib.parse.parse_qs(querystr)
        content_len = int(self.headers.get('content-length', 0))
        body = self.rfile.read(content_len)
        headers = self.headers.get_params()
        print(self)

        self.server.pipe.send({
            'path': path, 'query': query, 'body': body,
            'method': self.command, 'headers': headers,
        })
        if not self.server.pipe.poll(10):
            self.send_error(500, 'Pipe hung')

        status, headers, body = self.server.pipe.recv()
        if not isinstance(body, bytes):
            body = json.dumps(body).encode('utf8') + b'\n'

        self.send_response(status)
        for hn, hv in headers or ():
            self.send_header(hn, hv)
        self.end_headers()
        self.wfile.write(body)

    do_GET = _do_any
    do_PUT = _do_any
    do_POST = _do_any
    do_DELETE = _do_any
    do_PATCH = _do_any


def threadit(target, *args, **kw):
    t = Thread(target=target, name=target.__name__, args=args, kwargs=kw)
    t.daemon = True
    t.start()
    return t


def run(bind_at):
    p1, p2 = multiprocessing.Pipe()

    class MyTCPServer(TCPServer):
        allow_reuse_address = True
        pipe = p2

    httpd = MyTCPServer(bind_at, Handler)
    threadit(httpd.serve_forever)
    return p1


