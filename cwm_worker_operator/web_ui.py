import traceback
from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler

from cwm_worker_operator import config
from cwm_worker_operator import domains_config


def get_header(server):
    yield '<p><a href="/">index</a> | <a href="/domain/example007.com">domain</a> | <a href="/redis_key/worker:available:example007.com">redis key</a></p>'


def get_keys_summary(server, domain_name=None):
    for key in server.dc.get_keys_summary(domain_name=domain_name):
        yield "<b>{} ({})</b><br/>\n".format(key['title'], key['total'])
        for _key in key['keys']:
            yield "{}<br/>".format(_key)
        yield "<br/>"


def get_index(server):
    yield from get_header(server)
    yield from get_keys_summary(server)


def get_domain(server, domain_name):
    yield from get_header(server)
    if not domain_name:
        yield "Please input a domain name"
        return
    yield "<h3>Domain: {}</h3>".format(domain_name)
    if domain_name.startswith('delete/'):
        domain_name = domain_name.replace('delete/', '')
        server.dc.del_worker_keys(None, domain_name)
        yield '<p style="color:red;font-weight:bold;">Deleted all domain worker keys</p>'
    else:
        yield from get_keys_summary(server, domain_name)
        yield '<hr/>'
        yield '<p style="color:red;font-weight:bold;">Delete all domain worker keys? <a href="/domain/delete/{}">YES</a></p>'.format(domain_name)


def get_redis_key(server, key):
    yield from get_header(server)
    with server.dc.get_redis() as r:
        if key.startswith('delete/'):
            key = key.replace('delete/', '')
            r.delete(key)
            yield '<p style="color:red;font-weight:bold;">Deleted key: {}</p>'.format(key)
        elif key.startswith('set/'):
            *key, value = key.replace('set/', '').split('/')
            key = '/'.join(key)
            r.set(key, value)
            yield '<p style="color:red;font-weight:bold;">Key was set: {} = {}</p>'.format(key, value)
        else:
            value = r.get(key)
            if value:
                value = value.decode()
            yield "{} = {}<br/>".format(key, value)
            yield '<p style="color:red;font-weight:bold;"><a href="/redis_key/set/{}/VALUE">Set key (edit URL, replace VALUE)</a></p>'.format(key)
            yield '<p style="color:red;font-weight:bold;">Delete key? <a href="/redis_key/delete/{}">YES</a></p>'.format(key)


class CwmWorkerOperatorHTTPRequestHandler(BaseHTTPRequestHandler):

    def _send_html(self, html):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        for data in html:
            self.wfile.write(data.encode())

    def _send_server_error(self, error='Server Error'):
        self.send_response(500)
        self.end_headers()
        self.wfile.write(error.encode())

    def _send_request_error(self, error='Bad Request'):
        self.send_response(400)
        self.end_headers()
        self.wfile.write(error.encode())

    def do_GET(self):
        try:
            if self.path == '/':
                self._send_html(get_index(self.server))
            elif self.path.startswith('/domain/'):
                domain_name = self.path.replace('/domain/', '')
                self._send_html(get_domain(self.server, domain_name))
            elif self.path.startswith('/redis_key/'):
                key = self.path.replace('/redis_key/', '')
                self._send_html(get_redis_key(self.server, key))
            else:
                self._send_request_error()
        except:
            traceback.print_exc()
            self._send_server_error()


class CwmWorkerOperatorHTTPServer(HTTPServer):

    def __init__(self):
        self.dc = domains_config.DomainsConfig()
        super(CwmWorkerOperatorHTTPServer, self).__init__(('0.0.0.0', config.WEB_UI_PORT), CwmWorkerOperatorHTTPRequestHandler)


def start_daemon():
    print("Starting web UI on port {}".format(config.WEB_UI_PORT))
    CwmWorkerOperatorHTTPServer().serve_forever()
