import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class CliTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('duomove.__main__'), 'CLI is not implemented')

    def run_cli(self, *args):
        env = dict(os.environ)
        env.pop('DUOMOVE_SERVICE_TOKEN', None)
        return subprocess.run([sys.executable, '-m', 'duomove', *args], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=5)

    def test_status_says_motion_is_unavailable(self):
        r = self.run_cli('status')
        self.assertEqual(r.returncode, 0)
        payload = json.loads(r.stdout)
        self.assertFalse(payload['motion_enabled'])
        self.assertEqual(payload['mode'], 'diagnostics_only')

    def test_missing_adb_reports_unknown_capabilities(self):
        r = self.run_cli('probe', '--serial', 'example.test:5555', '--adb-binary', '/missing/adb')
        self.assertEqual(r.returncode, 1)
        report = json.loads(r.stdout)['report']
        self.assertEqual(report['status'], 'unavailable')
        self.assertIsNone(report['cmd_location']['field_flags']['speed'])
        self.assertFalse(report['location_delivery_verified'])

    def test_invalid_serial_is_redacted(self):
        r = self.run_cli('probe', '--serial', 'secret;command')
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stdout)['event'], 'error')
        self.assertNotIn('secret;command', r.stdout + r.stderr)

    def test_drive_is_not_silently_simulated(self):
        r = self.run_cli('drive', '--miles', '3')
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stdout)['event'], 'error')

    def test_serve_requires_token(self):
        r = self.run_cli('serve')
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stdout)['code'], 'invalid_configuration')

    def test_help(self):
        r = self.run_cli('--help')
        self.assertEqual(r.returncode, 0)
        self.assertIn('probe', r.stdout)
        self.assertIn('serve', r.stdout)

if __name__ == '__main__': unittest.main()
