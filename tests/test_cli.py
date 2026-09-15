import json
import os
import subprocess
import sys
from pathlib import Path


def run(*args, stdin=None):
    root = Path(__file__).parents[1]
    env = dict(os.environ, PYTHONPATH=str(root/'src'))
    return subprocess.run([sys.executable, '-m', 'duomove', *args], input=stdin, capture_output=True, text=True, env=env, timeout=10)


def test_help_cli_works():
    result = run('--help')
    assert result.returncode == 0
    assert 'parse-help' in result.stdout


def test_offline_parse_is_marked_offline():
    result = run('parse-help', stdin='  set-test-provider-location gps --location LAT,LON [--accuracy M]\n')
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data['source'] == 'offline_help'
    assert data['write_verified'] is False
    assert data['advertised_fields']['accuracy'] is True


def test_unknown_offline_help_is_failure_not_fake_support():
    result = run('parse-help', stdin='Permission denied')
    assert result.returncode == 2
    assert all(value is None for value in json.loads(result.stdout)['advertised_fields'].values())


def test_missing_adb_has_structured_failure(tmp_path):
    result = run('probe', '--serial', 'emulator-5554', '--device-id', 'test-device', '--adb', str(tmp_path/'absent-adb'))
    assert result.returncode == 2
    assert json.loads(result.stdout)['status'] == 'failed'
    assert 'emulator-5554' not in result.stdout


def test_no_live_execution_command():
    result = run('drive', '--miles', '3')
    assert result.returncode != 0


def test_invalid_serial_is_not_executed():
    result = run('probe', '--serial', 'a;reboot', '--device-id', 'test-device')
    assert result.returncode == 2
    assert json.loads(result.stdout)['error'] == 'invalid_configuration'


def test_output_is_exclusive_and_private(tmp_path):
    destination = tmp_path/'report.json'
    args = ('probe', '--serial', 'emulator-5554', '--device-id', 'test-device', '--adb', str(tmp_path/'missing'), '--output', str(destination))
    result = run(*args)
    assert result.returncode == 2
    assert destination.stat().st_mode & 0o777 == 0o600
    before = destination.read_bytes()
    result = run(*args)
    assert result.returncode == 2
    assert destination.read_bytes() == before
    assert json.loads(result.stdout)['error'] == 'output_exists'
