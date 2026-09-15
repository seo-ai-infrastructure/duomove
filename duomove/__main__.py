"""Run with python -m duomove. Operational output is JSON Lines."""
from __future__ import annotations

import argparse
import json

from . import __version__
from .probe import AdbRunner, run_probe


def emit(event: dict) -> None:
    print(json.dumps(event, separators=(',', ':'), allow_nan=False), flush=True)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error text can repeat arbitrary submitted secrets.
        emit({'event': 'error', 'code': 'invalid_arguments', 'hint': 'Use --help for supported options.'})
        raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    parser = Parser(description='DuoMove read-only ADB diagnostics. Motion execution is not enabled.')
    sub = parser.add_subparsers(dest='command', required=True, parser_class=Parser)
    sub.add_parser('status', help='Show local runtime scope; does not contact devices')
    probe = sub.add_parser('probe', help='Run fixed read-only diagnostics against an authorized device')
    probe.add_argument('--serial', required=True, help='ADB serial or host:port')
    probe.add_argument('--device-id', default='test-device', help='Non-sensitive alias used in the report')
    probe.add_argument('--connect', action='store_true', help='Explicitly establish ADB transport first')
    probe.add_argument('--adb-binary', default='adb', help='Local path to the adb executable')
    probe.add_argument('--timeout', type=float, default=8, help='Timeout per command, 1-30 seconds')
    sub.add_parser('serve', help='Start the authenticated HTTP service; requires DUOMOVE_SERVICE_TOKEN')
    args = parser.parse_args(argv)
    try:
        if args.command == 'status':
            emit({'service': 'duomove', 'version': __version__, 'mode': 'diagnostics_only',
                  'motion_enabled': False, 'original_motion_package_integrated': False})
            return 0
        if args.command == 'probe':
            runner = AdbRunner(args.serial, binary=args.adb_binary, timeout=args.timeout)
            report = run_probe(args.serial, device_id=args.device_id, connect=args.connect, runner=runner)
            emit({'event': 'probe_finished', 'report': report})
            return 0 if report['status'] == 'complete' else 1
        from .service import Settings, create_app
        import uvicorn
        settings = Settings.from_env()
        uvicorn.run(create_app(settings), host='0.0.0.0', port=settings.port,
                    workers=1, access_log=False, log_level='info')
        return 0
    except ValueError:
        emit({'event': 'error', 'code': 'invalid_configuration',
              'hint': 'Check serial, timeout, service token and server environment configuration.'})
        return 2
    except KeyboardInterrupt:
        emit({'event': 'cancelled'})
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
