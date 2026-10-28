"""Isolated Next.js -> official SDK -> production Caddyfile -> Liwan acceptance test.
Requires a built web/.next/standalone, installed Playwright Chromium, Caddy and Liwan.
No Docker daemon, real RiskLive data or production service is used.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def run(binary, caddy, output):
    with tempfile.TemporaryDirectory(prefix='risklive-liwan-integration-') as temporary, ExitStack() as stack:
        tmp = Path(temporary)
        def launch(command, env=None, cwd=None):
            log = stack.enter_context((tmp / f'process-{len(processes)}.log').open('w+'))
            proc = subprocess.Popen(command, env=env, cwd=cwd, stdout=log, stderr=log)
            processes.append(proc)
            def stop():
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
            stack.callback(stop)
            return proc
        processes = []
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def request(base, path, data=None, method=None, token=None):
            headers = {'Content-Type': 'application/json'}
            if token:
                headers['Authorization'] = f'Bearer {token}'
            req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None, headers=headers, method=method)
            with opener.open(req, timeout=40) as response:
                raw = response.read()
                return json.loads(raw) if response.headers.get_content_type() == 'application/json' and raw else raw.decode(errors='replace')
        def ready(base):
            for _ in range(200):
                try:
                    request(base, '/privacy' if base != liwan else '/')
                    return
                except OSError:
                    if any(p.poll() is not None for p in processes):
                        raise RuntimeError('\n'.join(p.read_text() for p in tmp.glob('process-*.log')))
                    time.sleep(.1)
            raise RuntimeError('Isolated server failed to start')
        liwan = f'http://127.0.0.1:{port()}'
        config = tmp / 'liwan.toml'
        config.write_text((ROOT / 'deployment/liwan/config.toml').read_text().replace('0.0.0.0:9042', liwan.removeprefix('http://')) + f'\n')
        env = dict(os.environ, LIWAN_BASE_URL=liwan, LIWAN_DATA_DIR=str(tmp / 'liwan-data'), LIWAN_CONFIG=str(config))
        password = secrets.token_urlsafe(24)
        subprocess.run([str(binary), 'add-user', 'synthetic', password, '--admin', 'true'], env=env, check=True, stdout=subprocess.DEVNULL)
        launch([str(binary)], env=env)
        ready(liwan)
        request(liwan, '/api/dashboard/auth/login', {'username': 'synthetic', 'password': password})
        settings = json.loads((ROOT / 'deployment/liwan/collection-settings.json').read_text())
        request(liwan, '/api/dashboard/settings', settings, 'PUT')
        request(liwan, '/api/dashboard/project/risklive', {'displayName': 'Synthetic', 'visibility': 'private', 'entities': []})
        request(liwan, '/api/dashboard/entity', {'id': 'risklive', 'displayName': 'Synthetic', 'projects': ['risklive']})
        key = request(liwan, '/api/dashboard/api-keys', {'displayName': 'Synthetic', 'entities': ['risklive'], 'projects': [], 'permissions': ['events:batch'], 'expiration': '7_days'})['plaintext']
        # Clone only the built application; its cwd and every source artifact are disposable.
        app = tmp / 'web'
        shutil.copytree(ROOT / 'web/.next/standalone', app, symlinks=True)
        shutil.copytree(ROOT / 'web/.next/static', app / '.next/static', dirs_exist_ok=True)
        shutil.copytree(ROOT / 'web/schema', app / 'schema', dirs_exist_ok=True)
        results = tmp / 'results'
        dashboard = results / 'web/dashboard.json'
        dashboard.parent.mkdir(parents=True)
        url = 'https://publisher.invalid/story?id=42'
        alert = {'title': 'Synthetic article', 'url': url + '&utm_source=alerts', 'alert_flag': 'Red'}
        leaf = {'name': 'Synthetic article', 'value': 1, 'meta': {'title': 'Synthetic article', 'url': url, 'alertFlag': 'Red', 'category': 'nuclear', 'topic': 'energy'}}
        dashboard.write_text(json.dumps({'generated_at': datetime.now(timezone.utc).isoformat(), 'alerts': {'nuclear': [], 'non_nuclear': {}},
            'recent_alerts': {'red': [], 'yellow': [], 'green': []}, 'flagged_alerts': {'red': [alert], 'yellow': []},
            'newsmap': {'name': 'All News', 'children': [{'name': 'nuclear', 'children': [{'name': 'Red', 'children': [leaf]}]}]},
            'topics': [{'keyword': 'first topic', 'response': 'Synthetic'}, {'keyword': 'second topic', 'response': 'Synthetic'}], 'topic_tree': ''}))
        # The existing dashboard API uses ISR. Seed only its disposable fixture cache
        # so the first browser request does not receive the build-time missing-file response.
        cached = app / '.next/server/app/api/dashboard'
        cached.with_suffix('.body').write_text(dashboard.read_text())
        meta = json.loads(cached.with_suffix('.meta').read_text())
        meta['status'] = 200
        cached.with_suffix('.meta').write_text(json.dumps(meta))
        timeline = results / 'web/newsmap/seca-light-30d'
        timeline.mkdir(parents=True)
        (timeline / 'manifest.json').write_text(json.dumps({'total_batches': 1, 'files': ['tree.json']}))
        (timeline / 'tree.json').write_text(json.dumps({'hkts': [{'hkt_id': 1, 'parent_node_id': 0, 'expected_words': [{'word_id': 1, 'token': 'energy'}], 'node_ids': [101]}],
            'nodes': [{'node_id': 101, 'hkt_id': 1, 'words': [{'word_id': 1, 'token': 'energy'}], 'top_words': [{'word_id': 1, 'token': 'energy'}],
                       'sources': [{'internal_source_id': 1, 'external_source_id': url}]}]}))
        csv = results / 'data/news_data.csv'
        csv.parent.mkdir()
        csv.write_text(f'Title,URL,Description,Timestamp,Query\nSynthetic article,{url},Synthetic,2026-10-27T00:00:00Z,Nuclear\n')
        web = f'http://127.0.0.1:{port()}'
        disabled = f'http://127.0.0.1:{port()}'
        for base, enabled in [(web, 'true'), (disabled, 'false')]:
            launch(['node', str(app / 'server.js')], env=dict(os.environ, PORT=base.rsplit(':', 1)[1], HOSTNAME='127.0.0.1',
                   NODE_ENV='production', LIWAN_ENABLED=enabled, LIWAN_ENTITY_ID='risklive', ANALYTICS_TEST_MODE='false', DASHBOARD_JSON_PATH=str(dashboard)))
            ready(base)
        edge = f'http://127.0.0.1:{port()}'
        caddy_env = dict(os.environ, CADDY_SITE_ADDRESS=edge, LIWAN_ENABLED='true', XDG_CONFIG_HOME=str(tmp), XDG_DATA_HOME=str(tmp))
        adapted = json.loads(subprocess.check_output([str(caddy), 'adapt', '--config', str(ROOT / 'deployment/caddy/Caddyfile.prod'), '--adapter', 'caddyfile'], env=caddy_env))
        adapted['admin'] = {'disabled': True, 'config': {'persist': False}}
        def upstreams(value):
            if isinstance(value, dict):
                if value.get('dial') == 'liwan:9042': value['dial'] = liwan.removeprefix('http://')
                if value.get('dial') == 'web:3000': value['dial'] = web.removeprefix('http://')
                for child in value.values(): upstreams(child)
            if isinstance(value, list):
                for child in value: upstreams(child)
        upstreams(adapted)
        caddy_config = tmp / 'caddy.json'
        caddy_config.write_text(json.dumps(adapted))
        launch([str(caddy), 'run', '--config', str(caddy_config)], env=caddy_env)
        ready(edge)
        browser = tmp / 'browser.json'
        subprocess.run(['node', str(ROOT / 'web/scripts/liwan-browser-test.mjs'), edge, disabled, str(browser)], check=True, timeout=150)
        evidence = json.loads(browser.read_text())
        article = next(e['properties']['article_id'] for e in evidence['captured'] if e['name'] == 'article_opened')
        # Exercise built-in ranking with 25 IDs, plus historical clicks on the UI-tested article.
        historical = []
        now = datetime.now(timezone.utc)
        for i in range(25):
            article_id = article if i == 0 else 'url-v1-' + hashlib.sha256(f'https://publisher.invalid/article/{i}'.encode()).hexdigest()
            for j in range(25 - i):
                historical.append({'name': 'article_opened', 'url': 'https://risklive.test/alerts',
                    'createdAt': (now - timedelta(days=30 + j % 3 * 30)).isoformat(),
                    'properties': {'article_id': article_id, 'section': 'alerts' if j % 2 == 0 else 'newsmap', 'risk_level': 'red' if j % 2 == 0 else 'yellow'}})
        request(liwan, '/api/v1/events', {'entityId': 'risklive', 'events': historical}, token=key)
        date_range = {'start': (now - timedelta(days=730)).isoformat(), 'end': (now + timedelta(days=1)).isoformat()}
        def report(dimension='article_id', filters=None, kind='dimension'):
            payload = {'range': date_range, 'filters': filters or [], 'event': 'article_opened', 'metric': 'views'}
            if kind == 'dimension': payload.update(dimension='property', propertyKey=dimension)
            else: payload.update(interval='month', timezone='UTC')
            return request(liwan, f'/api/dashboard/project/risklive/{kind}', payload)
        for _ in range(100):
            ranking = report()
            if sum(e['value'] for e in ranking['data']) == 328: break
            time.sleep(.1)
        assert sum(e['value'] for e in ranking['data']) == 328, ranking
        assert next(e['value'] for e in ranking['data'] if e['dimensionValue'] == article) == 28
        evidence['combinedArticleRanking'] = ranking
        evidence['top20'] = sorted(ranking['data'], key=lambda e: -e['value'])[:20]
        evidence['sections'] = report('section')
        evidence['risks'] = report('risk_level')
        evidence['articleMonthly'] = report(filters=[{'dimension': 'property', 'key': 'article_id', 'filterType': 'equal', 'value': article}], kind='graph')
        evidence['sectionFiltered'] = report(filters=[{'dimension': 'property', 'key': 'section', 'filterType': 'equal', 'value': 'newsmap'}])
        assert len(evidence['top20']) == 20
        assert sum(r['value'] for r in evidence['sectionFiltered']['data']) == 157
        assert next(r['value'] for r in evidence['sectionFiltered']['data'] if r['dimensionValue'] == article) == 13
        assert {r['dimensionValue']: r['value'] for r in evidence['risks']['data']} == {'red': 171, 'yellow': 156, 'unknown': 1}
        assert sum(r['value'] for r in evidence['articleMonthly']['data']) == 28
        assert len([r for r in evidence['articleMonthly']['data'] if r['value']]) >= 3
        assert {r['dimensionValue']: r['value'] for r in evidence['sections']['data']} == {'alerts': 170, 'newsmap': 157, 'newsmap-experimental': 1}
        denied = {}
        for path in ['/analytics/', '/analytics/api/dashboard/projects', '/analytics/api/v1/events', '/analytics/script.js', '/api/dashboard/auth/me']:
            try:
                request(edge, path)
                raise AssertionError('Public admin endpoint accessible: ' + path)
            except urllib.error.HTTPError as error:
                assert error.code == 404, (path, error.code)
                denied[path] = error.code
        evidence['publicAdministrativeRoutes'] = denied
        output.write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps({'checks': evidence['checks'], 'articleCombinedCount': 28, 'top20Rows': 20, 'publicAdminDenied': True, 'evidence': str(output)}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--caddy', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.binary.resolve(), args.caddy.resolve(), args.output.resolve())
