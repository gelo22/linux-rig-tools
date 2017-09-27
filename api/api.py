from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import json
import os
import subprocess


def get_data(debug=False):
    data = [
        dict(temp=54, fan=65),
        dict(temp=48, fan=70),
        os.listdir('.'),
    ]
    if debug:
        print(data)
    return data


class HttpRequestHandler(BaseHTTPRequestHandler):
    def _send_html(self, http_code, html):
        self.send_response(http_code)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def _send_json(self, data):
        try:
            res = json.dumps(data)
        except:
            self.send_response(500)
            return

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(res.encode('utf-8'))

    def do_GET(self):
        if self.path == '/api/v1':
            self._send_json(get_data(debug=True))
        else:
            self._send_html(200, '<h1>It works!</h1>')


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    def __init__(self, _host, _handler):
        super().__init__(_host, _handler)
        self.daemon_threads = True


print('Server listening on port 8000...')
httpd = ThreadedHTTPServer(('0.0.0.0', 8000), HttpRequestHandler)
httpd.serve_forever()
