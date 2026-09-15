"""CLI entrypoint; core parsing/probing does not need HTTP dependencies."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from .probe import AdbReader, MAX_OUTPUT_BYTES, parse_location_help, probe


def _emit(value: dict) -> None:
    print(json.dumps(value, allow_nan=False, separators=(",", ":")))


def _write_private(path: str, report: dict) -> None:
    # O_EXCL refuses existing files and symlinks; reports are private by default.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DuoMove read-only Android capability probe")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("parse-help", help="Parse saved cmd location help from stdin, without contacting a device")
    live = sub.add_parser("probe", help="Run four read-only commands on an already connected ADB serial")
    live.add_argument("--serial", required=True)
    live.add_argument("--device-id", required=True, help="Non-sensitive report alias, not an endpoint")
    live.add_argument("--adb", default="adb", help="Trusted local adb executable")
    live.add_argument("--timeout", type=float, default=10)
    live.add_argument("--output", help="Create a new private JSON report file; will not overwrite")
    server = sub.add_parser("serve", help="Run the authenticated internal probe API; no automatic device jobs")
    server.add_argument("--host", default="0.0.0.0")
    server.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == "parse-help":
            text = sys.stdin.read(MAX_OUTPUT_BYTES + 1)
            if len(text) > MAX_OUTPUT_BYTES:
                _emit({"error": "input_too_large"})
                return 2
            fields = parse_location_help(text)
            _emit({"schema_version": 1, "source": "offline_help", "advertised_fields": fields,
                   "write_verified": False, "device_location_observed": False})
            return 0 if fields["latitude"] is True else 2
        if args.command == "probe":
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.device_id):
                raise ValueError("Invalid device alias")
            if args.output and Path(args.output).exists():
                raise FileExistsError
            report = probe(AdbReader(args.serial, args.adb, args.timeout), args.device_id)
            if args.output:
                _write_private(args.output, report)
            _emit(report)
            return 0 if report["status"] == "complete" else 2
        if args.command == "serve":
            import uvicorn
            from .service import create_app
            port = args.port if args.port is not None else int(os.getenv("PORT", "8000"))
            if not 1 <= port <= 65535:
                raise ValueError("Invalid port")
            uvicorn.run(create_app(), host=args.host, port=port, workers=1,
                        access_log=False, server_header=False, proxy_headers=False)
            return 0
    except FileExistsError:
        _emit({"error": "output_exists"})
        return 2
    except (ValueError, TypeError):
        _emit({"error": "invalid_configuration"})
        return 2
    except OSError:
        _emit({"error": "local_io_failed"})
        return 2
    except KeyboardInterrupt:
        return 130
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
