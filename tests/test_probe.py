import json
import subprocess
import sys

import pytest

HELP = '''Location service commands:
  providers
    add-test-provider <PROVIDER> [--supportsAltitude] [--supportsSpeed] [--supportsBearing]
      Add a test provider.
    set-test-provider-enabled <PROVIDER> <ENABLED>
    set-test-provider-location <PROVIDER> --location <LATITUDE>,<LONGITUDE>
      [--accuracy <ACCURACY>] [--time <TIME>]
      Set location for the given test provider.
    send-extra-command <PROVIDER> <COMMAND>
      Future --speed option in an unrelated command.
'''

def test_parser_scopes_flags():
    from duomove.probe import parse_location_help
    fields = parse_location_help(HELP)
    assert fields['latitude'] is True
    assert fields['longitude'] is True
    assert fields['accuracy'] is True
    assert fields['time'] is True
    assert fields['altitude'] is False
    assert fields['speed'] is False
    assert fields['bearing'] is False

@pytest.mark.parametrize('text', ['', 'Permission denial', 'Unknown command', 'add-test-provider gps --supportsSpeed'])
def test_unknown_help_has_no_false_claims(text):
    from duomove.probe import parse_location_help
    assert all(value is None for value in parse_location_help(text).values())

def test_vendor_extra_flags_are_only_advertised():
    from duomove.probe import parse_location_help
    text = HELP.replace('[--time <TIME>]', '[--time <TIME>] [--altitude <M>] [--speed <MPS>] [--bearing <DEG>]')
    result = parse_location_help(text)
    assert result['altitude'] is result['speed'] is result['bearing'] is True

def test_prose_mentions_do_not_become_supported_flags():
    from duomove.probe import parse_location_help
    text = HELP.replace('Set location for the given test provider.', 'Set location. --altitude and --speed are not supported.')
    assert parse_location_help(text)['speed'] is False

@pytest.mark.parametrize('serial', ['', '-s', 'x;reboot', 'a\nb', 'a b', 'x$(id)', '/tmp/device', 'x`id`'])
def test_serial_validation(serial):
    from duomove.probe import AdbReader
    with pytest.raises(ValueError):
        AdbReader(serial)

def test_probe_runs_only_four_reads_and_hides_raw_data():
    from duomove.probe import CommandResult, READ_COMMANDS, probe
    class Fake:
        calls = []
        def read(self, command):
            self.calls.append(command)
            out = {'release': '15\n', 'sdk': '35\n', 'help': HELP,
                   'dump': 'Location Manager State: last fix latitude=SECRET phone-id=PRIVATE'}[command]
            return CommandResult(0, out, '', 1.0)
    reader = Fake()
    report = probe(reader, 'test-device')
    assert reader.calls == list(READ_COMMANDS)
    assert report['status'] == 'complete'
    assert report['android'] == {'release': '15', 'sdk': 35}
    assert report['location']['advertised_fields']['speed'] is False
    assert report['location']['write_verified'] is False
    assert report['motion_execution_enabled'] is False
    assert 'SECRET' not in json.dumps(report) and 'PRIVATE' not in json.dumps(report)
    assert report['location']['dumpsys_captured'] is True

def test_one_failed_read_does_not_stop_other_reads():
    from duomove.probe import CommandResult, probe
    class Fake:
        def read(self, command):
            return CommandResult(1, '', 'device unauthorized') if command == 'help' else CommandResult(0, '35', '')
    report = probe(Fake(), 'test-device')
    assert report['status'] == 'partial'
    assert all(x is None for x in report['location']['advertised_fields'].values())
    assert report['commands']['help']['error'] == 'device_unauthorized'
    assert len(report['commands']) == 4

@pytest.mark.parametrize('message,expected', [('error: device offline','device_offline'), ('device not found','device_not_found'), ('SecurityException permission denied','permission_denied'), ('unknown private content','command_failed')])
def test_error_classification_does_not_leak_text(message, expected):
    from duomove.probe import CommandResult, probe
    class Fake:
        def read(self, command):
            return CommandResult(1, '', message)
    report = probe(Fake(), 'test-device')
    assert report['status'] == 'failed'
    assert report['commands']['help']['error'] == expected
    assert message not in json.dumps(report)

def test_only_named_commands_are_accepted():
    from duomove.probe import AdbReader
    with pytest.raises(ValueError):
        AdbReader('emulator-5554').read('reboot')

def test_missing_adb_is_structured_failure(tmp_path):
    from duomove.probe import AdbReader, probe
    report = probe(AdbReader('emulator-5554', executable=str(tmp_path / 'missing-adb')), 'test-device')
    assert report['status'] == 'failed'
    assert report['commands']['release']['error'] == 'adb_not_found'


def test_timeout_and_subprocess_argv(monkeypatch):
    from duomove.probe import AdbReader
    def run(args, **kwargs):
        assert args == ['adb', '-s', 'emulator-5554', 'shell', 'cmd', 'location', '-h']
        assert kwargs['shell'] is False
        assert kwargs['timeout'] == 2
        raise subprocess.TimeoutExpired(args, 2)
    monkeypatch.setattr(subprocess, 'run', run)
    result = AdbReader('emulator-5554', timeout=2).read('help')
    assert result.error == 'timeout'


def test_truncated_help_is_unknown():
    from duomove.probe import CommandResult, probe
    class Fake:
        def read(self, command):
            return CommandResult(0, HELP, '', truncated=True)
    report = probe(Fake(), 'test-device')
    assert report['status'] != 'complete'
    assert report['commands']['help']['error'] == 'output_limit'
    assert all(x is None for x in report['location']['advertised_fields'].values())
