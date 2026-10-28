"""Use Liwan's existing private administration API; no custom reporting backend.

Credentials: LIWAN_ADMIN_USERNAME / LIWAN_ADMIN_PASSWORD, or interactive prompts.
Use only over localhost or an SSH tunnel. Never expose this tool as a web endpoint.
"""
import argparse
import getpass
import http.cookiejar
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['configure', 'prune'])
    parser.add_argument('--url', default='http://127.0.0.1:9042')
    parser.add_argument('--apply', action='store_true', help='apply pruning; default is a dry run')
    args = parser.parse_args()
    url = urllib.parse.urlsplit(args.url)
    if url.hostname not in ('localhost', '127.0.0.1', '::1') or url.scheme not in ('http', 'https') or url.username or url.password or url.path not in ('', '/'):
        parser.error('Use a loopback URL or an SSH tunnel, without credentials/path in the URL')
    username = os.environ.get('LIWAN_ADMIN_USERNAME') or input('Liwan admin username: ')
    password = os.environ.get('LIWAN_ADMIN_PASSWORD') or getpass.getpass('Liwan admin password: ')
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(path, data, method='POST'):
        req = urllib.request.Request(args.url.rstrip('/') + '/api/dashboard/' + path, data=json.dumps(data).encode(), method=method,
                                     headers={'Content-Type': 'application/json'})
        with client.open(req, timeout=120) as response:
            raw = response.read()
            return json.loads(raw) if raw else {'status': response.status}
    request('auth/login', {'username': username, 'password': password})
    try:
        if args.action == 'configure':
            settings = json.loads((ROOT / 'deployment/liwan/collection-settings.json').read_text())
            print(json.dumps(request('settings', settings, 'PUT'), indent=2))
            display = json.loads((ROOT / 'deployment/liwan/project-display-settings.json').read_text())
            print(json.dumps(request('project/risklive/settings', display, 'PUT'), indent=2))
        else:
            print(json.dumps(request('settings/prune', {'dryRun': not args.apply}), indent=2))
    finally:
        request('auth/logout', {})


if __name__ == '__main__':
    main()
