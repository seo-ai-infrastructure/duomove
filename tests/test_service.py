import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

TOKEN = 'test-only-token-abcdefghijklmnopqrstuvwxyz-123456'


def client(probe_fn=None, token=TOKEN, targets=None):
    from duomove.service import Settings, create_app
    settings = Settings(token=token, targets={'test-device': 'emulator-5554'} if targets is None else targets)
    return TestClient(create_app(settings, probe_fn=probe_fn))


def headers(token=TOKEN):
    return {'Authorization': f'Bearer {token}'}


def test_health_does_not_touch_device():
    def forbidden(*args):
        raise AssertionError('Health check invoked a probe')
    response = client(forbidden).get('/healthz')
    assert response.status_code == 200
    assert response.json()['mode'] == 'probe_only'


@pytest.mark.parametrize('authorization', [None, 'Bearer wrong', 'Basic wrong', 'Bearer '])
def test_authentication_required(authorization):
    def forbidden(*args):
        raise AssertionError('Unauthenticated probe')
    response = client(forbidden).post('/v1/probes/test-device', headers={'Authorization': authorization} if authorization else {})
    assert response.status_code == 401


def test_missing_token_fails_closed():
    assert client(token=None).post('/v1/probes/test-device', headers=headers()).status_code == 503


@pytest.mark.parametrize('token', ['short', 'a'*32+' ', 'é'*32])
def test_weak_or_invalid_token_rejected(token):
    from duomove.service import Settings
    with pytest.raises(ValueError):
        Settings(token=token, targets={})


def test_unknown_target_cannot_select_a_host():
    def forbidden(*args):
        raise AssertionError('Unknown target reached ADB')
    response = client(forbidden).post('/v1/probes/other-device', headers=headers())
    assert response.status_code == 404


def test_authorized_probe_uses_only_server_target():
    def fake(reader, device_id):
        assert reader.serial == 'emulator-5554'
        assert device_id == 'test-device'
        return {'status': 'complete', 'motion_execution_enabled': False}
    response = client(fake).post('/v1/probes/test-device', headers=headers())
    assert response.status_code == 200
    assert response.json()['motion_execution_enabled'] is False


def test_partial_probe_is_not_success_status():
    response = client(lambda *args: {'status': 'partial'}).post('/v1/probes/test-device', headers=headers())
    assert response.status_code == 502
    assert response.json()['status'] == 'partial'


def test_command_body_is_rejected():
    def forbidden(*args):
        raise AssertionError('Request with unsupported body reached ADB')
    response = client(forbidden).post('/v1/probes/test-device', json={'serial': 'elsewhere', 'command': 'reboot'}, headers=headers())
    assert response.status_code == 400


def test_status_requires_auth_and_does_not_claim_motion():
    c = client()
    assert c.get('/v1/status').status_code == 401
    response = c.get('/v1/status', headers=headers())
    assert response.json()['motion_execution_enabled'] is False
    assert response.json()['original_motion_source_integrated'] is False
    assert 'emulator-5554' not in response.text


def test_overlapping_probes_rejected():
    entered, release = threading.Event(), threading.Event()
    def fake(*args):
        entered.set()
        assert release.wait(5)
        return {'status': 'complete'}
    with client(fake) as c, ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(c.post, '/v1/probes/test-device', headers=headers())
        try:
            assert entered.wait(3)
            assert c.post('/v1/probes/test-device', headers=headers()).status_code == 409
        finally:
            release.set()
        assert first.result().status_code == 200


def test_exception_does_not_leak_and_releases_lock():
    def broken(*args):
        raise RuntimeError('super-secret-device-endpoint')
    c = client(broken)
    for _ in range(2):
        response = c.post('/v1/probes/test-device', headers=headers())
        assert response.status_code == 500
        assert 'super-secret' not in response.text


@pytest.mark.parametrize('targets', [['x'], {'bad alias': 'emulator-5554'}, {'test': 'host;reboot'}, {'test': 1}])
def test_invalid_server_mapping_rejected(targets):
    from duomove.service import Settings
    with pytest.raises(ValueError):
        Settings(token=TOKEN, targets=targets)


def test_invalid_environment_mapping(monkeypatch):
    from duomove.service import Settings
    monkeypatch.setenv('DUOMOVE_TARGETS_JSON', '{invalid')
    with pytest.raises(ValueError):
        Settings.from_environment()
