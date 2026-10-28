"""Isolated configuration/routing tests. No Docker daemon or production services."""
import http.client
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]


class LiwanDeployment(unittest.TestCase):
    def test_compose_is_opt_in_and_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / 'empty.env'
            env_file.touch()
            env = dict(os.environ, COMPOSE_PROJECT_NAME='risklive-analytics-validation',
                       APP_IMAGE='app:validation', WEB_IMAGE='web:validation',
                       APP_ENV_FILE=str(env_file), WEB_ENV_FILE=str(env_file),
                       CADDY_ENV_FILE=str(env_file), RISKLIVE_DATA_DIR=directory)
            result = subprocess.run(['docker', 'compose', '-f', str(ROOT / 'deployment/compose/docker-compose.prod.yml'),
                                     '--profile', 'analytics', 'config', '--format', 'json'],
                                    env=env, capture_output=True, text=True, check=True)
            config = json.loads(result.stdout)
        services = config['services']
        liwan = services['liwan']
        self.assertEqual(liwan['profiles'], ['analytics'])
        self.assertEqual(liwan['ports'][0]['host_ip'], '127.0.0.1')
        self.assertEqual(set(liwan['networks']), {'analytics'})
        self.assertTrue(config['networks']['analytics']['internal'])
        self.assertEqual(liwan['volumes'][0]['target'], '/data')
        self.assertEqual(liwan['volumes'][0]['type'], 'volume')
        self.assertIn('@sha256:', liwan['image'])
        self.assertEqual(set(services['caddy']['networks']), {'internal', 'analytics'})
        for name in ('app', 'scheduler', 'web'):
            self.assertNotIn('analytics', services[name]['networks'])
            self.assertNotIn('liwan', services[name].get('depends_on', {}))
        self.assertEqual([name for name, value in services.items() if any(p.get('host_ip', '0.0.0.0') != '127.0.0.1' for p in value.get('ports', []))], ['caddy'])

    def test_public_routing_and_payload_boundary(self):
        if not shutil.which(os.environ.get('CADDY_BINARY', 'caddy')):
            self.skipTest('caddy binary required')
        received = []

        class Upstream(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.path, dict(self.headers)))
                self.send_response(200)
                self.send_header('Set-Cookie', 'unwanted=1')
                self.end_headers()
                self.wfile.write(b'ok')

            def log_message(self, *args):
                pass

        upstream = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        thread.start()
        try:
            for enabled in (False, True):
                with self.subTest(enabled=enabled), tempfile.TemporaryDirectory() as directory:
                    with socket.socket() as sock:
                        sock.bind(('127.0.0.1', 0))
                        port = sock.getsockname()[1]
                    env = dict(os.environ, CADDY_SITE_ADDRESS=f'http://127.0.0.1:{port}',
                               LIWAN_ENABLED=str(enabled).lower())
                    adapted = subprocess.run([os.environ.get('CADDY_BINARY', 'caddy'), 'adapt', '--config', str(ROOT / 'deployment/caddy/Caddyfile.prod'),
                                              '--adapter', 'caddyfile'], env=env, capture_output=True, text=True, check=True)
                    config = json.loads(adapted.stdout)
                    config['admin'] = {'disabled': True, 'config': {'persist': False}}

                    def redirect_upstreams(value):
                        if isinstance(value, dict):
                            if 'dial' in value:
                                value['dial'] = f'127.0.0.1:{upstream.server_port}'
                            for child in value.values():
                                redirect_upstreams(child)
                        elif isinstance(value, list):
                            for child in value:
                                redirect_upstreams(child)

                    redirect_upstreams(config)
                    path = Path(directory) / 'caddy.json'
                    path.write_text(json.dumps(config))
                    with open(Path(directory) / 'caddy.log', 'w+') as log:
                        process = subprocess.Popen([os.environ.get('CADDY_BINARY', 'caddy'), 'run', '--config', str(path)], stdout=log, stderr=log,
                                                   env=dict(env, XDG_DATA_HOME=directory, XDG_CONFIG_HOME=directory))
                        try:
                            for _ in range(100):
                                try:
                                    with socket.create_connection(('127.0.0.1', port), timeout=.1):
                                        break
                                except OSError:
                                    if process.poll() is not None:
                                        log.seek(0)
                                        self.fail(log.read())
                                    time.sleep(.02)
                            cases = [('/analytics/event', 200 if enabled else 404),
                                     ('/analytics/event?debug=true', 404),
                                     ('/analytics/', 404), ('/analytics/login', 404),
                                     ('/analytics/api/dashboard/projects', 404),
                                     ('/analytics/api/v1/events', 404),
                                     ('/analytics/script.js', 404), ('/analytics/count', 404)]
                            for url, expected in cases:
                                before = len(received)
                                connection = http.client.HTTPConnection('127.0.0.1', port)
                                connection.request('POST', url, headers={'Cookie': 'id=private', 'Authorization': 'secret',
                                                                       'Referer': 'http://private/?search=secret'})
                                response = connection.getresponse()
                                response.read()
                                self.assertEqual(response.status, expected, url)
                                self.assertIsNone(response.getheader('Set-Cookie'))
                                connection.close()
                                if expected == 404:
                                    self.assertEqual(len(received), before)
                                else:
                                    request_path, headers = received[-1]
                                    self.assertEqual(request_path, '/api/event')
                                    self.assertEqual(headers['User-Agent'], 'RiskLiveAnalytics/1')
                                    for header in ('Cookie', 'Authorization', 'Referer'):
                                        self.assertNotIn(header, headers)
                            connection = http.client.HTTPConnection('127.0.0.1', port)
                            connection.request('GET', '/analytics/event')
                            response = connection.getresponse()
                            response.read()
                            self.assertEqual(response.status, 404)
                            connection.close()
                        finally:
                            process.terminate()
                            process.wait(timeout=5)
        finally:
            upstream.shutdown()
            upstream.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
