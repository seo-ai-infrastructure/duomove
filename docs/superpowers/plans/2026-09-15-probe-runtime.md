# DuoMove Probe Runtime Implementation Plan

> For agentic workers: use superpowers:executing-plans. Execute all local tests before publishing.

**Goal:** Publish a runnable read-only Android capability probe and Railway container configuration.

**Architecture:** Python core runs fixed ADB read commands; parser produces tri-state advertised capabilities. FastAPI authenticates an internal control plane and selects only configured device aliases. No motion implementation replaces the unavailable original package.

**Tech Stack:** Python >=3.12, standard-library subprocess, FastAPI 0.128.2, Uvicorn 0.48.0, pytest 9.0.2.

**Spec:** docs/superpowers/specs/2026-09-15-probe-design.md

## Global Constraints

No live device writes. No external commands from HTTP input. No token/serial/dumpsys leakage. Unknown capability is null. Actual motion integration remains pending source availability.

## Task 1: Parser and read-only runner

Files: src/duomove/probe.py, tests/test_probe.py.

- [x] Write tests for AOSP-style help, supportsSpeed-only help, unknown help, added optional flags, four-command allowlist, timeout, offline/unauthorized device, output truncation, and redacted reports.
- [x] Run `PYTHONPATH=src pytest tests/test_probe.py -q` and verify absent feature failures.
- [x] Implement `parse_location_help(text: str) -> dict`, `AdbReader(serial: str, executable: str = 'adb', timeout: float = 10)`, and `probe(reader, device_id: str) -> dict`.
- [x] Run the same test command and inspect every failure.

## Task 2: Authenticated service and CLI

Files: src/duomove/service.py, src/duomove/__main__.py, tests/test_service.py, tests/test_cli.py.

- [x] Write tests proving no probe runs without authentication, unknown aliases cannot invoke ADB, weak/missing tokens fail closed, overlapping probes return 409, /healthz does not touch devices, and offline help cannot masquerade as a live probe.
- [x] Run `PYTHONPATH=src pytest tests/test_service.py tests/test_cli.py -q` before implementation.
- [x] Implement `create_app(settings=None, probe_fn=None)` and CLI `python -m duomove parse-help`, `probe`, and `serve`.
- [x] Re-run all tests; execute both subprocess CLI and local HTTP smoke checks.

## Task 3: Package and publish

Files: pyproject.toml, Dockerfile, railway.toml, .env.example, .gitignore, .dockerignore, .github/workflows/ci.yml, README.md, docs/verification.md.

- [x] Pin dependencies. Configure exec-form Python startup, non-root user, distro ADB, /healthz Railway check, and one replica.
- [x] Run `PYTHONPATH=src pytest -q` and `python -m compileall -q src tests`.
- [x] Record actual interpreter/version/test results; mark Docker, Railway and real-device tests as not run unless independently executed.
- [x] Review files for secrets and private device data.
- [ ] Publish only project-owned source/config/docs to the existing feature branch and verify remote contents.
- [ ] Open a pull request; do not merge or deploy automatically.
