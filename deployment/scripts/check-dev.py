#!/usr/bin/env python3
"""Daemon-free Compose/lifecycle checks. Run separately from guarded Python suite."""
import os
import json
import shutil
import sqlite3
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'deployment/scripts/dev.sh'

def check(tmp_path):
    data = tmp_path / 'dev'
    env = dict(os.environ, RISKLIVE_DEV_DATA_DIR=str(data), COMPOSE_PROJECT_NAME='risklive-prod',
               COMPOSE_PROFILES='*', APP_ENV_FILE='/production/secrets')
    subprocess.run([SCRIPT, 'init'], env=env, check=True, capture_output=True)
    sentinel = data / 'runtime/test-artifact.txt'
    sentinel.write_text('persistent state')
    database = data / 'runtime/test.sqlite3'
    with sqlite3.connect(database) as conn:
        conn.execute('CREATE TABLE state (value TEXT)')
        conn.execute("INSERT INTO state VALUES ('preserved')")
    rag = data / 'results/rag'
    rag.mkdir()
    (rag / 'index.fixture').write_text('preserved index')
    resolved = subprocess.check_output([SCRIPT, 'config'], env=env, text=True)
    assert '8888' not in resolved and '/production' not in resolved
    assert 'risklive-dev-app:local' in resolved
    production_env = dict(env, COMPOSE_PROJECT_NAME='risklive-prod',
                          APP_ENV_FILE=str(data / 'env/app.env'),
                          WEB_ENV_FILE=str(data / 'env/web.env'),
                          CADDY_ENV_FILE=str(data / 'env/caddy.env'),
                          APP_IMAGE='app:production-check', WEB_IMAGE='web:production-check',
                          RISKLIVE_DATA_DIR=str(data), CADDY_HTTP_BIND='0.0.0.0:8888')
    production = json.loads(subprocess.check_output(
        ['docker', 'compose', '-f', str(ROOT / 'deployment/compose/docker-compose.prod.yml'),
         'config', '--format', 'json'], env=production_env, text=True))
    assert production['name'] == 'risklive-prod'
    assert str(production['services']['caddy']['ports'][0]['published']) == '8888'
    assert sentinel.read_text() == 'persistent state'
    assert subprocess.run([SCRIPT, 'init'], env=env, capture_output=True).returncode != 0
    assert subprocess.run([SCRIPT, 'live-test', 'python', '-m', 'app.scheduler'], env=env, capture_output=True).returncode != 0
    # Delegate ONLY config to real Compose. Record lifecycle commands without a daemon.
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    recorded = tmp_path / 'docker-calls.jsonl'
    docker = shutil.which('docker')
    wrapper = fake_bin / 'docker'
    wrapper.write_text('#!/usr/bin/env python3\nimport os, sys, json\n'
                       + 'if "config" in sys.argv: os.execv(' + repr(docker) + ', [' + repr(docker) + '] + sys.argv[1:])\n'
                       + 'with open(' + repr(str(recorded)) + ', "a") as out: out.write(json.dumps(sys.argv[1:]) + "\\n")\n')
    wrapper.chmod(0o755)
    fake_env = dict(env, PATH=str(fake_bin) + os.pathsep + os.environ['PATH'])
    for action in ('up', 'restart', 'down'):
        subprocess.run([SCRIPT, action], env=fake_env, check=True, capture_output=True)
        assert sentinel.read_text() == 'persistent state'
        with sqlite3.connect(database) as conn:
            assert conn.execute('SELECT value FROM state').fetchone() == ('preserved',)
        assert (rag / 'index.fixture').read_text() == 'preserved index'
    subprocess.run([SCRIPT, 'live-test', '--acknowledge-paid-api-calls', 'python', '-c', 'pass'],
                   env=fake_env, check=True, capture_output=True)
    calls = [json.loads(line) for line in recorded.read_text().splitlines()]
    assert len(calls) == 4
    for args in calls:
        assert args[args.index('--project-name') + 1] == 'risklive-dev'
        assert '-v' not in args and '--volumes' not in args
        assert 'scheduler' not in args
    assert calls[0][-3:] == ['app', 'web', 'caddy']
    assert '--no-deps' in calls[-1] and '--rm' in calls[-1]
    assert 'run' in calls[-1] and 'app' in calls[-1]
    # A symlink outside the data root fails before any Docker lifecycle operation.
    (data / 'results').rename(data / 'results-saved')
    (data / 'results').symlink_to(tmp_path)
    assert subprocess.run([SCRIPT, 'config'], env=env, capture_output=True).returncode != 0


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='risklive-dev-check-') as directory:
        check(Path(directory))
    print('Development Compose and lifecycle static checks passed')
