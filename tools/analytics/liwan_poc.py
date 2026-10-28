"""Run synthetic reports against an official Liwan binary; never contacts RiskLive.

Usage: python3 tools/analytics/liwan_poc.py --binary /tmp/.../liwan --output /tmp/evidence.json
Uses temporary data, ephemeral loopback HTTP, local credentials and built-in APIs only.
"""
import argparse
from collections import Counter
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

RANGE = {'start': '2024-11-01T00:00:00Z', 'end': '2026-11-01T00:00:00Z'}
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'


def prop(key, value):
    return {'dimension': 'property', 'key': key, 'filterType': 'equal', 'value': value, 'strict': True}


def synthetic_events():
    events = []
    for month in range(24):
        year, month_zero = divmod(2024 * 12 + 10 + month, 12)
        for article in range(1, 26):
            for click in range(26 - article + month // 6):
                section = ('alerts', 'newsmap', 'newsmap-experimental')[(click + article) % 3]
                name = 'alert_source_opened' if section == 'alerts' else 'newsmap_source_opened'
                events.append({'name': name, 'url': f'https://risklive.invalid/{section}',
                               'createdAt': f'{year}-{month_zero + 1:02d}-15T12:{click:02d}:00Z',
                               'ip': ('192.0.2.1', '198.51.100.1')[click % 2], 'userAgent': UA,
                               'properties': {'article_id': f'article-{article:03d}', 'section': section,
                                              'risk_level': ('red', 'yellow', 'unknown')[article % 3],
                                              'event_type': 'article_opened'}})
        for name, count in [('topic_selected', 9), ('newsmap_node_selected', 5), ('pageview', 12)]:
            for index in range(count):
                events.append({'name': name, 'url': 'https://risklive.invalid/topics',
                               'createdAt': f'{year}-{month_zero + 1:02d}-16T13:{index:02d}:00Z',
                               'ip': ('192.0.2.1', '198.51.100.1')[index % 2], 'userAgent': UA,
                               'properties': {'section': 'topics', 'event_type': name}})
    return events


def run(binary, output):
    evidence = {'release': 'liwan-v1.8.1', 'binarySha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                'range': RANGE, 'reports': {}, 'checks': {}}
    events = synthetic_events()
    evidence['syntheticEventCount'] = len(events)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                         urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with tempfile.TemporaryDirectory(prefix='risklive-liwan-poc-') as directory:
        directory = Path(directory)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        config = directory / 'config.toml'
        config.write_text(f'base_url = "{base}"\nlisten = "127.0.0.1:{port}"\ndata_dir = "{directory / "data"}"\ndisable_favicons = true\ndisable_ntp_check = true\n[duckdb]\nthreads = 2\nmemory_limit = "512MB"\n')
        password = secrets.token_urlsafe(24)
        subprocess.run([str(binary), '--config', str(config), 'add-user', 'poc', password, '--admin', 'true'],
                       check=True, stdout=subprocess.DEVNULL)

        def request(path, data=None, method=None, token=None):
            headers = {'Content-Type': 'application/json'}
            if token:
                headers['Authorization'] = f'Bearer {token}'
            req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None,
                                         headers=headers, method=method)
            try:
                with opener.open(req, timeout=40) as response:
                    body = response.read()
                    return response.status, json.loads(body) if body and response.headers.get_content_type() == 'application/json' else body.decode(errors='replace')
            except urllib.error.HTTPError as error:
                body = error.read().decode(errors='replace')
                try:
                    body = json.loads(body)
                except ValueError:
                    pass
                return error.code, body

        def ok(path, data=None, method=None, token=None):
            status, response = request(path, data, method, token)
            assert 200 <= status < 300, (path, status, response)
            return response

        command = [str(binary), '--config', str(config)]
        trace = directory / 'connect.trace'
        if shutil.which('strace'):
            command = ['strace', '-f', '-e', 'trace=connect', '-o', str(trace), *command]
        with (directory / 'server.log').open('w+') as log:
            process = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
            try:
                for _ in range(200):
                    try:
                        request('/')
                        break
                    except OSError:
                        if process.poll() is not None:
                            log.seek(0)
                            raise RuntimeError(log.read())
                        time.sleep(.05)
                ok('/api/dashboard/auth/login', {'username': 'poc', 'password': password})
                settings = {'visitorGroupMode': 'network_standard', 'trackSessions': False, 'trackUtmParams': False,
                            'trackGeo': 'none', 'dataRetention': {'mode': 'days', 'days': 730}, 'ingestDropRules': []}
                ok('/api/dashboard/settings', settings, 'PUT')
                evidence['collectionSettings'] = ok('/api/dashboard/settings')
                for project in ('risklive-poc', 'canonical-control'):
                    ok(f'/api/dashboard/project/{project}', {'displayName': project, 'visibility': 'private', 'entities': []})
                    ok('/api/dashboard/entity', {'id': project, 'displayName': project, 'projects': [project]})
                key = ok('/api/dashboard/api-keys', {'displayName': 'synthetic-only', 'entities': ['risklive-poc', 'canonical-control'],
                         'projects': ['risklive-poc', 'canonical-control'], 'permissions': ['events:batch'],
                         'expiration': '7_days'})['plaintext']
                for entity, payload in [('risklive-poc', events), ('canonical-control',
                         [dict(event, name='article_opened') if event['properties']['event_type'] == 'article_opened' else event for event in events])]:
                    accepted = 0
                    for offset in range(0, len(payload), 1000):
                        result = ok('/api/v1/events', {'entityId': entity, 'events': payload[offset:offset + 1000]}, token=key)
                        accepted += result['accepted']
                        assert result['filtered'] == 0, result
                    assert accepted == len(payload)
                # Wait for the built-in event queue; no direct database writes or SQL reporting.
                for project in ('risklive-poc', 'canonical-control'):
                    for _ in range(300):
                        stats = ok(f'/api/dashboard/project/{project}/stats', {'range': RANGE, 'filters': [], 'event': 'pageview'})
                        if stats['stats']['totalViews'] == 288:
                            break
                        time.sleep(.1)
                    assert stats['stats']['totalViews'] == 288, (project, stats)

                def report(label, kind, event=None, filters=None, property_key=None, project='risklive-poc', **extra):
                    payload = {'range': RANGE, 'filters': filters or [], **extra}
                    if kind != 'custom-events':
                        payload['metric'] = 'views'
                        if event is not None:
                            payload['event'] = event
                    if kind == 'dimension':
                        payload.update(dimension='property', propertyKey=property_key)
                    status, response = request(f'/api/dashboard/project/{project}/{kind}', payload)
                    evidence['reports'][label] = {'project': project, 'endpoint': kind, 'request': payload,
                                                  'status': status, 'response': response}
                    return status, response

                for event in ('alert_source_opened', 'newsmap_source_opened'):
                    status, response = report(event + '_ranking', 'dimension', event, property_key='article_id')
                    expected = Counter(e['properties']['article_id'] for e in events if e['name'] == event)
                    evidence['checks'][event + '_ranking'] = status == 200 and {r['dimensionValue']: r['value'] for r in response.get('data', [])} == dict(expected)
                for section in ('alerts', 'newsmap', 'newsmap-experimental'):
                    name = 'alert_source_opened' if section == 'alerts' else 'newsmap_source_opened'
                    status, response = report(section + '_ranking', 'dimension', name, [prop('section', section)], 'article_id')
                    expected = Counter(e['properties']['article_id'] for e in events if e['name'] == name and e['properties']['section'] == section)
                    evidence['checks'][section + '_ranking'] = status == 200 and {r['dimensionValue']: r['value'] for r in response.get('data', [])} == dict(expected)
                status, response = report('risk_levels', 'dimension', 'alert_source_opened', property_key='risk_level')
                expected = Counter(e['properties']['risk_level'] for e in events if e['name'] == 'alert_source_opened')
                evidence['checks']['risk_levels'] = status == 200 and {r['dimensionValue']: r['value'] for r in response.get('data', [])} == dict(expected)
                for event in ('alert_source_opened', 'newsmap_source_opened'):
                    status, response = report(event + '_article_monthly', 'graph', event, [prop('article_id', 'article-001')],
                                              interval='month', timezone='UTC')
                    expected = Counter(e['createdAt'][:7] for e in events if e['name'] == event and e['properties'].get('article_id') == 'article-001')
                    evidence['checks'][event + '_monthly'] = status == 200 and {r['binStart'][:7]: r['value'] for r in response.get('data', [])} == dict(expected)
                status, response = report('features', 'custom-events')
                expected = Counter(e['name'] for e in events if e['name'] != 'pageview')
                evidence['checks']['feature_totals'] = status == 200 and {r['name']: r['completions'] for r in response.get('rows', [])} == dict(expected)
                report('article_property_without_event', 'dimension', property_key='article_id')
                report('article_property_wildcard_event', 'dimension', '*', property_key='article_id')
                report('article_property_multi_event', 'dimension', ['alert_source_opened', 'newsmap_source_opened'], property_key='article_id')
                status, response = report('canonical_combined_ranking', 'dimension', 'article_opened', property_key='article_id', project='canonical-control')
                expected = Counter(e['properties']['article_id'] for e in events if e['properties']['event_type'] == 'article_opened')
                evidence['checks']['canonical_ranking'] = status == 200 and {r['dimensionValue']: r['value'] for r in response.get('data', [])} == dict(expected)
                status, response = report('canonical_article_monthly', 'graph', 'article_opened', [prop('article_id', 'article-001')],
                       project='canonical-control', interval='month', timezone='UTC')
                expected = Counter(e['createdAt'][:7] for e in events if e['properties'].get('article_id') == 'article-001')
                evidence['checks']['canonical_monthly'] = status == 200 and {r['binStart'][:7]: r['value'] for r in response.get('data', [])} == dict(expected)
                status, response = report('multiple_property_filters', 'dimension', 'newsmap_source_opened',
                       [prop('section', 'newsmap'), prop('risk_level', 'red')], 'article_id')
                expected = Counter(e['properties']['article_id'] for e in events if e['name'] == 'newsmap_source_opened' and e['properties']['section'] == 'newsmap' and e['properties']['risk_level'] == 'red')
                evidence['checks']['multiple_property_filters'] = status == 200 and {r['dimensionValue']: r['value'] for r in response.get('data', [])} == dict(expected)
                report('approximate_uniques', 'stats', 'pageview')
                old = {'name': 'retention_probe', 'url': 'https://risklive.invalid/topics', 'createdAt': '2020-01-01T00:00:00Z'}
                ok('/api/v1/events', {'entityId': 'risklive-poc', 'events': [old]}, token=key)
                for _ in range(100):
                    probe = ok('/api/dashboard/project/risklive-poc/custom-events', {'range': {'start': '2019-01-01T00:00:00Z', 'end': '2021-01-01T00:00:00Z'}, 'filters': []})
                    if probe['rows']:
                        break
                    time.sleep(.1)
                evidence['expiredEventBeforePrune'] = probe
                evidence['pruneDryRun'] = ok('/api/dashboard/settings/prune', {'dryRun': True})
                evidence['pruneApplied'] = ok('/api/dashboard/settings/prune', {'dryRun': False})
                evidence['checks']['explicit_retention_prune'] = evidence['pruneDryRun']['total']['deletedEvents'] == 1 and evidence['pruneApplied']['total']['deletedEvents'] == 1
                after = ok('/api/dashboard/project/risklive-poc/custom-events', {'range': {'start': '2019-01-01T00:00:00Z', 'end': '2021-01-01T00:00:00Z'}, 'filters': []})
                evidence['expiredEventAfterPrune'] = after
                evidence['checks']['expired_event_removed'] = after['rows'] == []
                # Logged-out access must not disclose the private project's reports.
                ok('/api/dashboard/auth/logout', {})
                status, response = request('/api/dashboard/project/risklive-poc/stats', {'range': RANGE, 'filters': []}, token=key)
                evidence['apiKeyReportQuery'] = {'status': status, 'response': response}
                evidence['anonymousPrivateReportStatus'] = request('/api/dashboard/project/risklive-poc/stats', {'range': RANGE, 'filters': []})[0]
            finally:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=15)
        evidence['networkConnectAttempts'] = [line.split(' ', 1)[-1] for line in trace.read_text().splitlines() if 'connect(' in line] if trace.exists() else None
        evidence['checks']['no_server_outbound_connects_observed'] = evidence['networkConnectAttempts'] == []
        # Cold-copy BOTH embedded databases after graceful shutdown, then query the restore.
        backup = directory / 'backup'
        shutil.copytree(directory / 'data', backup)
        config.write_text(config.read_text().replace(str(directory / 'data'), str(backup)))
        with (directory / 'restore.log').open('w+') as log:
            restored = subprocess.Popen([str(binary), '--config', str(config)], stdout=log, stderr=log)
            try:
                for _ in range(100):
                    try:
                        request('/')
                        break
                    except OSError:
                        time.sleep(.05)
                ok('/api/dashboard/auth/login', {'username': 'poc', 'password': password})
                result = ok('/api/dashboard/project/canonical-control/stats', {'range': RANGE, 'filters': [], 'event': 'article_opened'})
                evidence['coldBackupRestoredStats'] = result
                evidence['checks']['cold_backup_restore'] = result['stats']['totalViews'] == 8700
            finally:
                restored.terminate()
                restored.wait(timeout=15)
        evidence['databaseFiles'] = sorted(str(p.relative_to(directory / 'data')) for p in (directory / 'data').rglob('*') if p.is_file())
        output.write_text(json.dumps(evidence, indent=2) + '\n')
        assert all(evidence['checks'].values()), evidence['checks']
        print(json.dumps({'eventsPerEntity': len(events), 'checks': evidence['checks'], 'evidence': str(output)}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.binary.resolve(), args.output.resolve())
