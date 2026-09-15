import importlib
import importlib.util
import json
import sys
import unittest

HELP = '''Location service commands:
  add-test-provider <NAME> [--supportsAltitude] [--supportsSpeed] [--supportsBearing]
  set-test-provider-location <NAME> --location <LAT>,<LON>
    [--accuracy <M>] [--time <MS>]
  send-extra-command <NAME> <COMMAND> [--speed 99]
'''

class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('duomove'), 'DuoMove is not implemented')
        self.p = importlib.import_module('duomove.probe')

    def fake_runner(self, overrides=None):
        p = self.p
        outputs = {
            'get_state': 'device\n', 'android_release': '15\n',
            'android_sdk': '35\n', 'location_help': HELP,
            'location_dump': 'Location Manager State:\nlast location: SECRET-COORDINATES',
            'connect': 'connected to example.test:5555',
        }
        outputs.update(overrides or {})
        class Runner:
            calls = None
            def __init__(self): self.calls = []
            def run(self, name):
                self.calls.append(name)
                value = outputs[name]
                return value if isinstance(value, p.CommandResult) else p.CommandResult('ok', 0, value, None)
        return Runner()

    def test_provider_properties_do_not_populate_sample_flags(self):
        data = self.p.parse_location_help(HELP)
        self.assertTrue(data['recognized'])
        self.assertEqual(data['field_flags'], {
            'lat_lon': True, 'accuracy': True, 'time': True,
            'altitude': False, 'speed': False, 'bearing': False,
        })
        self.assertFalse(data['delivery_verified'])

    def test_vendor_extension_is_advertised_not_verified(self):
        data = self.p.parse_location_help(HELP.replace('[--accuracy <M>]', '[--altitude <M>] [--speed <MPS>] [--bearing <DEG>]'))
        self.assertTrue(data['field_flags']['speed'])
        self.assertTrue(data['field_flags']['altitude'])
        self.assertFalse(data['delivery_verified'])

    def test_missing_or_unrecognized_help_stays_unknown(self):
        for text in ['', 'unknown command', 'add-test-provider gps --supportsSpeed', 'set-test-provider-location without arguments']:
            with self.subTest(text=text):
                result = self.p.parse_location_help(text)
                self.assertFalse(result['recognized'])
                self.assertTrue(all(v is None for v in result['field_flags'].values()))

    def test_probe_has_only_read_commands_and_no_raw_output(self):
        runner = self.fake_runner()
        result = self.p.run_probe('example.test:5555', device_id='lab', runner=runner)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['android'], {'release': '15', 'sdk': 35})
        self.assertEqual(runner.calls, ['get_state', 'android_release', 'android_sdk', 'location_help', 'location_dump'])
        self.assertNotIn('SECRET-COORDINATES', json.dumps(result))
        self.assertNotIn('example.test', json.dumps(result))
        self.assertTrue(result['read_only'])
        self.assertFalse(result['location_delivery_verified'])

    def test_offline_stops_before_android_commands(self):
        runner = self.fake_runner({'get_state': 'offline'})
        result = self.p.run_probe('example.test:5555', device_id='lab', runner=runner)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(runner.calls, ['get_state'])
        self.assertIsNone(result['cmd_location']['field_flags']['speed'])

    def test_failed_help_is_not_unsupported(self):
        failure = self.p.CommandResult('error', 1, 'permission denial SECRET', 'command_failed')
        result = self.p.run_probe('example.test:5555', device_id='lab', runner=self.fake_runner({'location_help': failure}))
        self.assertEqual(result['status'], 'partial')
        self.assertIsNone(result['cmd_location']['field_flags']['speed'])
        self.assertNotIn('SECRET', json.dumps(result))

    def test_invalid_sdk_does_not_complete(self):
        result = self.p.run_probe('example.test:5555', device_id='lab', runner=self.fake_runner({'android_sdk': 'unknown'}))
        self.assertEqual(result['status'], 'partial')
        self.assertIsNone(result['android']['sdk'])

    def test_transport_connection_is_explicit(self):
        runner = self.fake_runner()
        self.p.run_probe('example.test:5555', device_id='lab', connect=True, runner=runner)
        self.assertEqual(runner.calls[0], 'connect')

    def test_invalid_serials_are_rejected_before_runner(self):
        for serial in ['-s', 'foo;id', 'host:0', 'host:65536', 'a b', 'host:abc', '$(id)', 'https://host:5555']:
            with self.subTest(serial=serial):
                runner = self.fake_runner()
                with self.assertRaises(ValueError):
                    self.p.run_probe(serial, device_id='lab', runner=runner)
                self.assertEqual(runner.calls, [])

    def test_fixed_command_allowlist(self):
        runner = self.p.AdbRunner('example.test:5555')
        with self.assertRaises(ValueError): runner.run('install')
        with self.assertRaises(ValueError): runner.run('set_location')

    def test_missing_binary_is_a_redacted_failure(self):
        result = self.p.execute(['/definitely/missing/adb'], timeout=1)
        self.assertEqual(result.error, 'executable_missing')
        self.assertNotIn('/definitely', json.dumps(result.summary()))

    def test_timeout_terminates_local_child(self):
        result = self.p.execute([sys.executable, '-c', 'import time; time.sleep(10)'], timeout=0.1)
        self.assertEqual(result.error, 'timeout')

    def test_output_limit_terminates_local_child(self):
        result = self.p.execute([sys.executable, '-c', 'print("x" * 100000)'], max_bytes=1024)
        self.assertEqual(result.error, 'output_limit')
        self.assertLessEqual(len(result.output.encode()), 1024)

    def test_nonzero_exit_is_not_success(self):
        result = self.p.execute([sys.executable, '-c', 'raise SystemExit(7)'])
        self.assertEqual(result.status, 'error')
        self.assertEqual(result.returncode, 7)

    def test_successful_local_child(self):
        result = self.p.execute([sys.executable, '-c', 'print("15")'])
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.output.strip(), '15')

if __name__ == '__main__': unittest.main()
