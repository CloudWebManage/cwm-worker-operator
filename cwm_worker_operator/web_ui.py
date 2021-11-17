"""
A web interfacte for debugging
"""
import json
import traceback
from http.server import ThreadingHTTPServer
from http.server import BaseHTTPRequestHandler

from cwm_worker_operator import config, common
from cwm_worker_operator import domains_config


def get_header(is_api, server):
    if is_api:
        yield {
            'header': True,
            'index': '/api/',
            'worker': '/api/worker/<WORKER_ID>',
            'hostname': '/api/hostname/<HOSTNAME>',
            'redis key': '/api/redis_key/<POOL>/<REDIS_KEY>',
            'nodes': '/api/nodes',
        }
    else:
        yield '<p>' + ' | '.join([
            '<a href="/">index</a>',
            '<a href="/worker/cldtst">worker</a>',
            '<a href="/hostname/loadtest.cwmc-eu-test2.cloudwm-obj.com">hostname</a>',
            '<a href="/redis_key/ingress/hostname:error:loadtest.cwmc-eu-test2.cloudwm-obj.com">redis key</a>',
            '<a href="/nodes">nodes</a>',
        ]) + '</p>'


def get_keys_summary(is_api, server, worker_id=None, hostname=None):
    for key in server.dc.get_keys_summary(worker_id=worker_id, hostname=hostname, is_api=is_api):
        if key:
            if is_api:
                yield {k: v for k, v in key.items() if k in ['title', 'total', 'keys']}
            else:
                yield "<b>{} ({})</b><br/>\n".format(key['title'], key['total'])
                for _key in key['keys']:
                    yield "{}<br/>".format(_key)
                yield "<br/>"


def get_index(is_api, server):
    yield from get_header(is_api, server)
    yield from get_keys_summary(is_api, server)


def get_worker(is_api, server, worker_id):
    yield from get_header(is_api, server)
    if not worker_id:
        yield "Please input a worker id" if not is_api else {'error': 'missing worker id'}
        return
    if not is_api:
        yield "<h3>Worker ID: {}</h3>".format(worker_id)
    if worker_id.startswith('delete/'):
        worker_id = worker_id.replace('delete/', '')
        server.dc.del_worker_keys(worker_id)
        if is_api:
            yield {'ok': True, 'msg': 'Deleted all worker keys'}
            yield {'footer': True, 'back to worker': '/api/worker/{}'.format(worker_id)}
        else:
            yield '<p style="color:red;font-weight:bold;">Deleted all worker keys</p>' \
                  '<p><a href="/worker/{}">back to worker</a></p>'.format(worker_id)
    else:
        yield from get_keys_summary(is_api, server, worker_id)
        if is_api:
            yield {'footer': True, 'delete all worker keys': '/api/worker/delete/{}'.format(worker_id)}
        else:
            yield '<hr/>'
            yield '<p style="color:red;font-weight:bold;">Delete all worker keys? (may includes hostname keys not displayed here!) <a href="/worker/delete/{}">YES</a></p>'.format(worker_id)


def get_hostname(is_api, server, hostname):
    yield from get_header(is_api, server)
    if not hostname:
        yield "Please input a hostname" if not is_api else {'error': 'missing hostname'}
        return
    if not is_api:
        yield "<h3>Hostname: {}</h3>".format(hostname)
    if hostname.startswith('delete/'):
        hostname = hostname.replace('delete/', '')
        server.dc.del_worker_hostname_keys(hostname)
        if is_api:
            yield {'ok': True, 'msg': 'Deleted all hostname keys (related worker keys were not deleted!)'}
            yield {'footer': True, 'back to hostname': '/api/hostname/{}'.format(hostname)}
        else:
            yield '<p style="color:red;font-weight:bold;">Deleted all hostname keys (related worker keys were not deleted!)</p>' \
                  '<p><a href="/hostname/{}">back to hostname</a></p>'.format(hostname)
    else:
        yield from get_keys_summary(is_api, server, hostname=hostname)
        if is_api:
            yield {'footer': True, 'delete all hostname keys': '/api/hostname/delete/{}'.format(hostname)}
        else:
            yield '<hr/>'
            yield '<p style="color:red;font-weight:bold;">Delete all hostname keys? (will not delete related worker keys!) <a href="/hostname/delete/{}">YES</a></p>'.format(hostname)


def get_redis_key(is_api, server, pool, key):
    yield from get_header(is_api, server)
    with getattr(server.dc, 'get_{}_redis'.format(pool))() as r:
        if key.startswith('delete/'):
            key = key.replace('delete/', '')
            r.delete(key)
            if is_api:
                yield {'ok': True, 'msg': 'deleted key'}
            else:
                yield '<p style="color:red;font-weight:bold;">Deleted key: {}</p>'.format(key)
        elif key.startswith('set/'):
            *key, value = key.replace('set/', '').split('/')
            key = '/'.join(key)
            r.set(key, value)
            if is_api:
                yield {'ok': True, 'msg': 'key was set'}
            else:
                yield '<p style="color:red;font-weight:bold;">Key was set: {} = {}</p>'.format(key, value)
        else:
            value = r.get(key)
            if value:
                value = value.decode()
            if is_api:
                yield {'key': key, 'value': value}
            else:
                yield "{} = {}<br/>".format(key, value)
            if is_api:
                yield {'footer': True,
                       'set key': '/api/redis_key/{}/set/{}/<VALUE>'.format(pool, key),
                       'delete key': '/api/redis_key/{}/delete/{}'.format(pool, key)}
            else:
                yield '<p style="color:red;font-weight:bold;"><a href="/redis_key/{}/set/{}/VALUE">Set key (edit URL, replace VALUE)</a></p>'.format(pool, key)
                yield '<p style="color:red;font-weight:bold;">Delete key? <a href="/redis_key/{}/delete/{}">YES</a></p>'.format(pool, key)


def get_nodes(is_api, server):
    yield from get_header(is_api, server)
    nodes = {}
    with server.dc.get_internal_redis() as r:
        for key in map(bytes.decode, r.keys('node:nas:*')):
            _, _, key, node, nas_ip = key.split(':')
            if key == 'is_healthy':
                nodes.setdefault(node, {}).setdefault('nas_ips', {}).setdefault(nas_ip, {})['nas_healthy'] = True
            elif key == 'last_check':
                nodes.setdefault(node, {}).setdefault('nas_ips', {}).setdefault(nas_ip, {})['nas_last_check'] = server.dc.keys.node_nas_last_check.get('{}:{}'.format(node, nas_ip))
    with server.dc.get_ingress_redis() as r:
        for key in r.keys('node:healthy:*'):
            _, _, node_name = key.split(':')
            nodes.setdefault(node, {})['healthy'] = True
    if not is_api:
        yield '<table border="1" cellpadding="3">'
        yield '<tr><td><b>node</b></td><td><b>status</b></td><td><b>nas_status</b></td></tr>'
    for node_name, node_data in nodes.items():
        node_statuses = []
        if not node_data.get('healthy'):
            node_statuses.append('not healthy')
        node_nas_statuses = []
        for nas_ip, nas_data in node_data.get('nas_ips', {}).items():
            if not nas_data.get('nas_healthy', False):
                node_nas_statuses.append('{}: not healthy'.format(nas_ip))
            if not nas_data.get('nas_last_check') or (common.now() - nas_data['nas_last_check']).total_seconds() > 3600:
                node_nas_statuses.append('{}: no last check in past 1 hour'.format(nas_ip))
        if is_api:
            yield {'node_name': node_name, 'node_statuses': node_statuses, 'node_nas_statuses': node_nas_statuses}
        else:
            yield '<tr><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
                node_name,
                ', '.join(node_statuses) if node_statuses else 'OK',
                ', '.join(node_nas_statuses) if node_nas_statuses else 'OK'
            )
    if not is_api:
        yield '</table>'

class CwmWorkerOperatorHTTPRequestHandler(BaseHTTPRequestHandler):

    def _send_response(self, res):
        if self.is_api:
            self._send_json(res)
        else:
            self._send_html(res)

    def _send_json(self, res):
        if config.DEBUG:
            print("start send_json")
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        if config.DEBUG:
            print("start send_json write")
        self.wfile.write(b'[\n')
        for data in res:
            self.wfile.write(json.dumps(data).encode())
            self.wfile.write(b',\n')
        self.wfile.write(b'null]')
        if config.DEBUG:
            print("end send_html")

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
            self.is_api = self.path.startswith('/api')
            if self.is_api:
                self.path = self.path.replace('/api', '', 1)
                if not self.path:
                    self.path = '/'
            if self.path == '/':
                self._send_response(get_index(self.is_api, self.server))
            elif self.path.startswith('/worker/'):
                worker_id = self.path.replace('/worker/', '')
                self._send_response(get_worker(self.is_api, self.server, worker_id))
            elif self.path.startswith('/hostname/'):
                hostname = self.path.replace('/hostname/', '')
                self._send_response(get_hostname(self.is_api, self.server, hostname))
            elif self.path.startswith('/redis_key/'):
                pool, *key = self.path.replace('/redis_key/', '').split('/')
                key = '/'.join(key)
                self._send_response(get_redis_key(self.is_api, self.server, pool, key))
            elif self.path.startswith('/nodes'):
                self._send_response(get_nodes(self.is_api, self.server))
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
