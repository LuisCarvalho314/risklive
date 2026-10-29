"""Validate resolved Compose without contacting the Docker daemon."""
import json
from pathlib import Path
import sys


def validate(config, root, live=False):
    root = Path(root)
    assert root.is_absolute() and root.resolve() == root, 'Root must be canonical, without symlinks'
    assert config['name'] == 'risklive-dev'
    services = config['services']
    for name, service in services.items():
        for mount in service.get('volumes', []):
            if not mount.get('read_only', False):
                # Disabled analytics uses an unused project-scoped named volume.
                if name == 'liwan' and mount['type'] == 'volume':
                    continue
                assert mount['type'] == 'bind', (name, mount)
                source = Path(mount['source'])
                assert source.resolve().is_relative_to(root), (name, source)
        assert not service.get('container_name')
        if name != 'caddy':
            assert not service.get('ports') or name == 'liwan'
    for name in ('app', 'web'):
        service = services[name]
        is_live_app = live and name == 'app'
        assert set(service['networks']) == ({'dev_live'} if is_live_app else {'internal'})
        assert service['environment']['RISKLIVE_EXTERNAL_APIS_ENABLED'] == ('true' if is_live_app else 'false')
        assert service['image'].startswith(f'risklive-dev-{name}:')
    assert config['networks']['internal']['internal'] is True
    ports = services['caddy']['ports']
    assert len(ports) == 1 and ports[0]['host_ip'] == '127.0.0.1'
    assert str(ports[0]['published']) == '8188' and ports[0]['target'] == 80
    assert services['scheduler']['profiles'] == ['development-scheduler-forbidden']
    assert 'exit 1' in services['scheduler']['entrypoint'][-1]
    assert services['app']['environment']['RISKLIVE_ENVIRONMENT'] == 'development'


if __name__ == '__main__':
    validate(json.load(sys.stdin), sys.argv[1], '--live' in sys.argv[2:])
