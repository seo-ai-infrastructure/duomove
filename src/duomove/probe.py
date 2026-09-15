"""Fixed, read-only ADB diagnostics; advertised syntax is not injection proof."""
from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Protocol

READ_COMMANDS = MappingProxyType({
    "release": ("shell", "getprop", "ro.build.version.release"),
    "sdk": ("shell", "getprop", "ro.build.version.sdk"),
    "help": ("shell", "cmd", "location", "-h"),
    "dump": ("shell", "dumpsys", "location"),
})
FIELDS = ("latitude", "longitude", "accuracy", "time", "altitude", "speed", "bearing")
MAX_OUTPUT_BYTES = 128 * 1024


def parse_location_help(text: str) -> dict[str, bool | None]:
    """Read only the command synopsis, not capability/prose/other command flags."""
    unknown = dict.fromkeys(FIELDS)
    lines = text.splitlines()
    synopsis: list[str] = []
    for index, line in enumerate(lines):
        if re.match(r"^\s*(?:providers\s+)?set-test-provider-location\b", line):
            synopsis.append(line)
            for following in lines[index + 1:]:
                stripped = following.strip()
                if stripped.startswith(("[", "--")):
                    synopsis.append(stripped)
                else:
                    break
            break
    flags = set(re.findall(r"(?<![\w-])--([A-Za-z][A-Za-z0-9-]*)\b", " ".join(synopsis)))
    if "location" not in flags:
        return unknown
    return {field: ("location" if field in ("latitude", "longitude") else field) in flags
            for field in FIELDS}


@dataclass(frozen=True)
class CommandResult:
    returncode: int | None
    stdout: str
    stderr: str
    duration_ms: float = 0
    error: str | None = None
    truncated: bool = False


class Reader(Protocol):
    def read(self, command: str) -> CommandResult: ...


class AdbReader:
    """Use an already authorized ADB connection; do not connect or configure it."""
    def __init__(self, serial: str, executable: str = "adb", timeout: float = 10):
        valid = isinstance(serial, str) and re.fullmatch(
            r"(?:[A-Za-z0-9][A-Za-z0-9._:\[\]-]{0,254}|\[[A-Fa-f0-9:]+\]:[0-9]{1,5})", serial
        )
        if not valid:
            raise ValueError("Invalid ADB serial")
        if not 0.1 <= timeout <= 30:
            raise ValueError("ADB timeout must be between 0.1 and 30 seconds")
        self.serial, self.executable, self.timeout = serial, executable, timeout

    def read(self, command: str) -> CommandResult:
        if command not in READ_COMMANDS:
            raise ValueError("Unsupported probe command")
        args = [self.executable, "-s", self.serial, *READ_COMMANDS[command]]
        started = time.monotonic()
        # Temporary files bound memory use even for a large dumpsys response.
        # Only a limited prefix is read; truncated output can never verify a capability.
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            try:
                result = subprocess.run(
                    args, shell=False, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                    timeout=self.timeout, check=False,
                )
            except FileNotFoundError:
                return CommandResult(None, "", "", error="adb_not_found")
            except subprocess.TimeoutExpired:
                return CommandResult(None, "", "", error="timeout")
            except OSError:
                return CommandResult(None, "", "", error="adb_launch_failed")
            stdout.seek(0)
            stderr.seek(0)
            out, err = stdout.read(MAX_OUTPUT_BYTES + 1), stderr.read(MAX_OUTPUT_BYTES + 1)
            return CommandResult(
                result.returncode, out[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
                err[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
                round((time.monotonic() - started) * 1000, 3),
                truncated=len(out) > MAX_OUTPUT_BYTES or len(err) > MAX_OUTPUT_BYTES,
            )


def _error(result: CommandResult) -> str | None:
    if result.error:
        return result.error
    if result.truncated:
        return "output_limit"
    combined = f"{result.stderr}\n{result.stdout}".lower()
    for needle, label in (
        ("unauthorized", "device_unauthorized"), ("device offline", "device_offline"),
        ("not found", "device_not_found"), ("no devices", "device_not_found"),
        ("permission denied", "permission_denied"), ("permission denial", "permission_denied"),
        ("securityexception", "permission_denied"),
    ):
        # A normal location dump can mention app permissions; only classify errors
        # from a failed process or an explicit error/exception prefix.
        is_error_text = result.returncode != 0 or combined.lstrip().startswith(
            ("error:", "exception", "java.lang.securityexception", "securityexception", "permission denial")
        )
        if needle in combined and is_error_text:
            return label
    return "command_failed" if result.returncode != 0 else None


def probe(reader: Reader, device_id: str) -> dict:
    results = {name: reader.read(name) for name in READ_COMMANDS}
    errors = {name: _error(result) for name, result in results.items()}
    capabilities = parse_location_help(results["help"].stdout) if errors["help"] is None else dict.fromkeys(FIELDS)
    if errors["help"] is None and all(x is None for x in capabilities.values()):
        errors["help"] = "unrecognized_help"
    release = results["release"].stdout.strip() if errors["release"] is None else None
    if release is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,63}", release):
        release, errors["release"] = None, "invalid_release"
    sdk = results["sdk"].stdout.strip() if errors["sdk"] is None else ""
    if not 1 <= len(sdk) <= 3 or not sdk.isdecimal() or not 1 <= int(sdk) <= 100:
        if errors["sdk"] is None:
            errors["sdk"] = "invalid_sdk"
        sdk_value = None
    else:
        sdk_value = int(sdk)
    if errors["dump"] is None and not results["dump"].stdout.strip():
        errors["dump"] = "empty_output"
    succeeded = sum(error is None for error in errors.values())
    return {
        "schema_version": 1, "source": "adb_read_only_probe", "device_id": device_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if succeeded == 4 else "failed" if succeeded == 0 else "partial",
        "android": {"release": release, "sdk": sdk_value},
        "location": {"advertised_fields": capabilities, "write_verified": False,
                     "dumpsys_captured": errors["dump"] is None, "device_location_observed": False},
        "motion_execution_enabled": False,
        "commands": {name: {"ok": errors[name] is None, "error": errors[name],
                             "returncode": result.returncode, "duration_ms": result.duration_ms,
                             "stdout_bytes": len(result.stdout.encode("utf-8")),
                             "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest()}
                     for name, result in results.items()},
    }
