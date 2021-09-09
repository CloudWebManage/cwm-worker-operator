"""
A web interfacte for debugging
"""
import traceback
from http.server import ThreadingHTTPServer
from http.server import BaseHTTPRequestHandler

from cwm_worker_operator import config
from cwm_worker_operator import domains_config


def get_header(server):
    yield '<p>' + ' | '.join([
        '<a href="/">index</a>',
        '<a href="/worker/cldtst">worker</a>',
        '<a href="/hostname/loadtest.cwmc-eu-test2.cloudwm-obj.com">hostname</a>',
        '<a href="/redis_key/ingress/hostname:error:loadtest.cwmc-eu-test2.cloudwm-obj.com">redis key</a>'
    ]) + '</p>'


def get_keys_summary(server, worker_id=None, hostname=None):
    for key in server.dc.get_keys_summary(worker_id=worker_id, hostname=hostname):
        if key:
            yield "<b>{} ({})</b><br/>\n".format(key['title'], key['total'])
            for _key in key['keys']:
                yield "{}<br/>".format(_key)
            yield "<br/>"


def get_index(server):
    yield from get_header(server)
    yield from get_keys_summary(server)


def get_worker(server, worker_id):
    yield from get_header(server)
    if not worker_id:
        yield "Please input a worker id"
        return
    yield "<h3>Worker ID: {}</h3>".format(worker_id)
    if worker_id.startswith('delete/'):
        worker_id = worker_id.replace('delete/', '')
        server.dc.del_worker_keys(worker_id)
        yield '<p style="color:red;font-weight:bold;">Deleted all worker keys</p>' \
              '<p><a href="/worker/{}">back to worker</a></p>'.format(worker_id)
    else:
        yield from get_keys_summary(server, worker_id)
        yield '<hr/>'
        yield '<p style="color:red;font-weight:bold;">Delete all worker keys? (may includes hostname keys not displayed here!) <a href="/worker/delete/{}">YES</a></p>'.format(worker_id)


def get_hostname(server, hostname):
    yield from get_header(server)
    if not hostname:
        yield "Please input a hostname"
        return
    yield "<h3>Hostname: {}</h3>".format(hostname)
    if hostname.startswith('delete/'):
        hostname = hostname.replace('delete/', '')
        server.dc.del_worker_hostname_keys(hostname)
        yield '<p style="color:red;font-weight:bold;">Deleted all hostname keys (related worker keys were not deleted!)</p>' \
              '<p><a href="/hostname/{}">back to hostname</a></p>'.format(hostname)
    else:
        yield from get_keys_summary(server, hostname=hostname)
        yield '<hr/>'
        yield '<p style="color:red;font-weight:bold;">Delete all hostname keys? (will not delete related worker keys!) <a href="/hostname/delete/{}">YES</a></p>'.format(hostname)


def get_redis_key(server, pool, key):
    yield from get_header(server)
    with getattr(server.dc, 'get_{}_redis'.format(pool))() as r:
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
            yield '<p style="color:red;font-weight:bold;"><a href="/redis_key/{}/set/{}/VALUE">Set key (edit URL, replace VALUE)</a></p>'.format(pool, key)
            yield '<p style="color:red;font-weight:bold;">Delete key? <a href="/redis_key/{}/delete/{}">YES</a></p>'.format(pool, key)


class CwmWorkerOperatorHTTPRequestHandler(BaseHTTPRequestHandler):

    def _send_html(self, html):
        if config.DEBUG:
            print("start send_html")
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        if config.DEBUG:
            print("start send_html write")
        for data in html:
            self.wfile.write(data.encode())
        if config.DEBUG:
            print("end send_html")

    def _send_server_error(self, error='Server Error', status_code=500):
        if config.DEBUG:
            print("start send_server_error({} {})".format(status_code, error))
        self.send_response(status_code)
        self.end_headers()
        if config.DEBUG:
            print("start send_server_error write")
        self.wfile.write(error.encode())
        if config.DEBUG:
            print("end send_server_error")

    def _send_request_error(self, error='Bad Request'):
        self._send_server_error(error, 400)

    def do_GET(self):
        if config.DEBUG:
            print("Start do_GET ({})".format(self.path))
        try:
            if self.path == '/':
                self._send_html(get_index(self.server))
            elif self.path.startswith('/worker/'):
                worker_id = self.path.replace('/worker/', '')
                self._send_html(get_worker(self.server, worker_id))
            elif self.path.startswith('/hostname/'):
                hostname = self.path.replace('/hostname/', '')
                self._send_html(get_hostname(self.server, hostname))
            elif self.path.startswith('/redis_key/'):
                pool, *key = self.path.replace('/redis_key/', '').split('/')
                key = '/'.join(key)
                self._send_html(get_redis_key(self.server, pool, key))
            else:
                self._send_request_error()
        except:
            traceback.print_exc()
            self._send_server_error()


class CwmWorkerOperatorHTTPServer(ThreadingHTTPServer):

    def __init__(self):
        self.dc = domains_config.DomainsConfig()
        super(CwmWorkerOperatorHTTPServer, self).__init__(('0.0.0.0', config.WEB_UI_PORT), CwmWorkerOperatorHTTPRequestHandler)


def start_daemon():
    print("Starting web UI on port {}".format(config.WEB_UI_PORT))
    CwmWorkerOperatorHTTPServer().serve_forever()
