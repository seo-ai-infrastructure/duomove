import importlib
import importlib.util
import json
import threading
import unittest
from fastapi.testclient import TestClient

TOKEN = 'test-only-not-a-secret-' + 'a' * 32
AUTH = {'Authorization': 'Bearer ' + TOKEN}

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('duomove.service'), 'HTTP service is not implemented')
        self.s = importlib.import_module('duomove.service')
        self.calls = []
        def probe(serial, *, device_id, connect=False):
            self.calls.append((serial, device_id, connect))
            return {'status': 'complete', 'read_only': True, 'device_id': device_id}
        self.probe = probe
        self.settings = self.s.Settings(token=TOKEN, targets={'lab': 'example.test:5555'})
        self.client = TestClient(self.s.create_app(self.settings, probe=probe))

    def test_health_is_not_fleet_readiness(self):
        result = self.client.get('/healthz')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['scope'], 'http_service_only')
        self.assertFalse(result.json()['motion_enabled'])
        self.assertEqual(self.calls, [])

    def test_authentication_is_required(self):
        for method, path in [('get', '/v1/status'), ('post', '/v1/probes'), ('post', '/v1/motion')]:
            self.assertEqual(getattr(self.client, method)(path).status_code, 401)
        self.assertEqual(self.calls, [])

    def test_wrong_token_rejected(self):
        r = self.client.get('/v1/status', headers={'Authorization': 'Bearer wrong'})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.headers['www-authenticate'], 'Bearer')

    def test_status_never_exposes_tokens_or_endpoints(self):
        r = self.client.get('/v1/status', headers=AUTH)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['configured_devices'], ['lab'])
        self.assertNotIn(TOKEN, r.text)
        self.assertNotIn('example.test', r.text)
        self.assertEqual(r.headers['cache-control'], 'no-store')

    def test_allowlisted_alias_runs_probe(self):
        r = self.client.post('/v1/probes', headers=AUTH, json={'device_id': 'lab'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.calls, [('example.test:5555', 'lab', False)])

    def test_unknown_alias_is_rejected(self):
        r = self.client.post('/v1/probes', headers=AUTH, json={'device_id': 'other'})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.calls, [])

    def test_arbitrary_host_and_shell_options_not_accepted(self):
        for body in [{'device_id': 'lab', 'serial': 'internal:5555'},
                     {'device_id': 'lab', 'command': 'install bad.apk'},
                     {'device_id': 'lab', 'api_key': 'PRIVATE'},
                     {'device_id': 'lab', 'connect': True}]:
            r = self.client.post('/v1/probes', headers=AUTH, json=body)
            self.assertEqual(r.status_code, 422)
            self.assertNotIn('PRIVATE', r.text)
        self.assertEqual(self.calls, [])

    def test_secrets_not_reflected_in_validation_errors(self):
        r = self.client.post('/v1/probes', headers=AUTH, json={'device_id': 'private credential $100'})
        self.assertEqual(r.status_code, 422)
        self.assertNotIn('private credential', r.text)

    def test_motion_fails_instead_of_simulating(self):
        r = self.client.post('/v1/motion', headers=AUTH, json={'device_id': 'lab', 'action': 'drive'})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['detail'], 'motion_executor_not_integrated')
        self.assertEqual(self.calls, [])

    def test_cooldown_blocks_repeated_probes(self):
        a = self.client.post('/v1/probes', headers=AUTH, json={'device_id': 'lab'})
        b = self.client.post('/v1/probes', headers=AUTH, json={'device_id': 'lab'})
        self.assertEqual(a.status_code, 200)
        self.assertEqual(b.status_code, 429)
        self.assertIn('retry-after', b.headers)
        self.assertEqual(len(self.calls), 1)

    def test_single_active_probe(self):
        started, finish = threading.Event(), threading.Event()
        def slow_probe(*args, **kwargs):
            started.set()
            finish.wait(3)
            return {'status': 'complete'}
        client = TestClient(self.s.create_app(self.settings, probe=slow_probe))
        statuses = []
        worker = threading.Thread(target=lambda: statuses.append(client.post('/v1/probes', headers=AUTH, json={'device_id': 'lab'}).status_code))
        worker.start()
        try:
            self.assertTrue(started.wait(2))
            self.assertEqual(client.post('/v1/probes', headers=AUTH, json={'device_id': 'lab'}).status_code, 409)
        finally:
            finish.set()
            worker.join(4)
        self.assertEqual(statuses, [200])

    def test_probe_exception_is_redacted(self):
        def bad_probe(*args, **kwargs): raise RuntimeError('SECRETENDPOINT PRIVATEKEY')
        client = TestClient(self.s.create_app(self.settings, probe=bad_probe))
        r = client.post('/v1/probes', headers=AUTH, json={'device_id': 'lab'})
        self.assertEqual(r.status_code, 502)
        self.assertNotIn('SECRET', r.text)
        self.assertNotIn('PRIVATE', r.text)

    def test_settings_fail_closed(self):
        for token in ['', 'short', 'x' * 300, 'a' * 40 + ' ', 'a' * 40 + '☃']:
            with self.assertRaises(ValueError): self.s.Settings(token=token, targets={})

    def test_settings_environment_validation(self):
        settings = self.s.Settings.from_env({'DUOMOVE_SERVICE_TOKEN': TOKEN, 'DUOMOVE_ADB_TARGETS_JSON': '{"lab":"example.test:5555"}', 'PORT': '8080'})
        self.assertEqual(settings.port, 8080)
        self.assertFalse(settings.connect)
        for bad in ['[]', '{', '{"lab":"evil;id"}', '{"lab":123}']:
            with self.assertRaises(ValueError): self.s.Settings.from_env({'DUOMOVE_SERVICE_TOKEN': TOKEN, 'DUOMOVE_ADB_TARGETS_JSON': bad})

    def test_settings_repr_hides_token_and_targets(self):
        self.assertNotIn(TOKEN, repr(self.settings))
        self.assertNotIn('example.test', repr(self.settings))

    def test_public_docs_are_disabled(self):
        for path in ['/docs', '/redoc', '/openapi.json']:
            self.assertEqual(self.client.get(path).status_code, 404)

if __name__ == '__main__': unittest.main()
