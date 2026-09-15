"""Fixed-command ADB diagnostics. This module never creates a location provider."""
from __future__ import annotations

import hashlib
import os
import re
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

FIELD_FLAGS = {
    'lat_lon': '--location', 'accuracy': '--accuracy', 'time': '--time',
    'altitude': '--altitude', 'speed': '--speed', 'bearing': '--bearing',
}
READ_COMMANDS = {
    'get_state': ('get-state',),
    'android_release': ('shell', 'getprop', 'ro.build.version.release'),
    'android_sdk': ('shell', 'getprop', 'ro.build.version.sdk'),
    'location_help': ('shell', 'cmd', 'location', '-h'),
    'location_dump': ('shell', 'dumpsys', 'location'),
}


@dataclass(frozen=True)
class CommandResult:
    status: str
    returncode: int | None
    output: str = field(repr=False)
    error: str | None = None

    def summary(self) -> dict:
        """Exclude raw location dumps, addresses and arbitrary error messages."""
        encoded = self.output.encode('utf-8')
        return {
            'status': self.status, 'returncode': self.returncode, 'error': self.error,
            'retained_bytes': len(encoded),
            'retained_output_sha256': hashlib.sha256(encoded).hexdigest(),
        }


def execute(argv: list[str], timeout: float = 8, max_bytes: int = 262144) -> CommandResult:
    """Bound a local child by time and retained output. Linux/macOS only.

    Callers in this package construct argv from a fixed allowlist. This low-level
    helper is deliberately not exposed as an HTTP operation.
    """
    if os.name != 'posix':
        return CommandResult('error', None, '', 'unsupported_host_os')
    if timeout <= 0 or max_bytes < 1:
        raise ValueError('timeout and max_bytes must be positive')
    allowed_env = {'PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'ADB_VENDOR_KEYS'}
    env = {k: v for k, v in os.environ.items() if k in allowed_env}
    try:
        child = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, shell=False, start_new_session=True, env=env,
        )
    except FileNotFoundError:
        return CommandResult('error', None, '', 'executable_missing')
    except OSError:
        return CommandResult('error', None, '', 'process_start_failed')

    output = bytearray()
    deadline = time.monotonic() + timeout
    error = None
    try:
        assert child.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    error = 'timeout'
                    break
                for key, _ in selector.select(timeout=min(remaining, 0.1)):
                    block = os.read(key.fd, 65536)
                    if not block:
                        selector.unregister(key.fileobj)
                        continue
                    room = max_bytes - len(output)
                    output.extend(block[:room])
                    if len(block) > room:
                        error = 'output_limit'
                        break
                if error:
                    break
        if error is None:
            try:
                child.wait(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                error = 'timeout'
    finally:
        # Kill only this subprocess group, never the shared ADB server explicitly.
        if error or child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        child.wait()
        if child.stdout is not None:
            child.stdout.close()

    text = output.decode('utf-8', errors='replace')
    if error:
        return CommandResult('error', child.returncode, text, error)
    if child.returncode:
        return CommandResult('error', child.returncode, text, 'command_failed')
    if re.search(r'(?im)^\s*(?:error:|permission denial:|java\.lang\.SecurityException|Security exception:|cmd: Can.t find service)', text):
        return CommandResult('error', child.returncode, text, 'command_rejected')
    return CommandResult('ok', 0, text)


def validate_serial(serial: str) -> str:
    """Allow a USB/emulator serial or DNS/IPv4 host:port, never shell syntax."""
    if not isinstance(serial, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,252}', serial):
        raise ValueError('invalid ADB serial')
    if ':' in serial:
        host, sep, port = serial.partition(':')
        if not sep or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', host):
            raise ValueError('invalid ADB endpoint')
        if not port.isascii() or not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError('invalid ADB port')
    return serial


class Runner(Protocol):
    def run(self, name: str) -> CommandResult: ...


class AdbRunner:
    def __init__(self, serial: str, *, binary: str = 'adb', timeout: float = 8):
        self.serial = validate_serial(serial)
        if not 1 <= timeout <= 30:
            raise ValueError('ADB timeout must be between 1 and 30 seconds')
        self.binary = binary
        self.timeout = timeout

    def run(self, name: str) -> CommandResult:
        if name == 'connect':
            if ':' not in self.serial:
                raise ValueError('connect requires a host:port endpoint')
            return execute([self.binary, 'connect', self.serial], timeout=self.timeout)
        if name not in READ_COMMANDS:
            raise ValueError('ADB command is not on the read-only allowlist')
        return execute([self.binary, '-s', self.serial, *READ_COMMANDS[name]], timeout=self.timeout)


def parse_location_help(text: str) -> dict:
    """Read advertised sample arguments, not provider-property capabilities.

    A syntactically valid help section still proves neither authorization nor
    app-visible location delivery. Missing help is unknown, not unsupported.
    """
    result = {
        'recognized': False, 'source': 'cmd_location_help',
        'field_flags': dict.fromkeys(FIELD_FLAGS), 'advertised_flags': [],
        'delivery_verified': False, 'mock_authorization': 'not_checked',
    }
    match = re.search(r'(?m)^([ \t]*)(?:providers\s+)?set-test-provider-location\b[^\n]*', text)
    if not match:
        return result
    indent = len(match.group(1).expandtabs())
    section = [match.group(0)]
    for line in text[match.end():].splitlines():
        if not line.strip():
            continue
        line_indent = len(line) - len(line.lstrip(' \t'))
        if line_indent <= indent:
            break
        section.append(line)
    flags = set(re.findall(r'--[A-Za-z][A-Za-z0-9-]*', '\n'.join(section)))
    if '--location' not in flags:
        return result
    result.update({
        'recognized': True,
        'advertised_flags': sorted(flags),
        'field_flags': {name: flag in flags for name, flag in FIELD_FLAGS.items()},
    })
    return result


def run_probe(serial: str, *, device_id: str, connect: bool = False,
              runner: Runner | None = None) -> dict:
    """Return a redacted diagnostic report; raw outputs never leave this function."""
    validate_serial(serial)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', device_id):
        raise ValueError('invalid device alias')
    runner = runner or AdbRunner(serial)
    report = {
        'schema_version': 1, 'device_id': device_id,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'evidence_scope': 'adb_command_diagnostics',
        'status': 'unavailable', 'read_only': True,
        'location_delivery_verified': False,
        'android': {'release': None, 'sdk': None},
        'cmd_location': parse_location_help(''), 'checks': {},
    }
    if connect:
        connection = runner.run('connect')
        report['checks']['connect'] = connection.summary()
        if connection.status != 'ok':
            return report
    state = runner.run('get_state')
    report['checks']['get_state'] = state.summary()
    if state.status != 'ok' or state.output.strip() != 'device':
        return report

    results = {}
    for name in ('android_release', 'android_sdk', 'location_help', 'location_dump'):
        results[name] = runner.run(name)
        report['checks'][name] = results[name].summary()
    release = results['android_release']
    if release.status == 'ok' and re.fullmatch(r'[A-Za-z0-9._-]{1,32}', release.output.strip()):
        report['android']['release'] = release.output.strip()
    sdk = results['android_sdk']
    if sdk.status == 'ok' and re.fullmatch(r'[0-9]{1,3}', sdk.output.strip()):
        report['android']['sdk'] = int(sdk.output.strip())
    help_result = results['location_help']
    if help_result.status == 'ok':
        report['cmd_location'] = parse_location_help(help_result.output)
    complete = (
        all(item.status == 'ok' and item.output.strip() for item in results.values())
        and report['android']['release'] is not None
        and report['android']['sdk'] is not None
        and report['cmd_location']['recognized']
    )
    report['status'] = 'complete' if complete else 'partial'
    return report
