# DuoMove Read-only Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Publish a tested, runnable Python diagnostic CLI and Railway service without changing device location.

**Architecture:** A fixed-command ADB runner produces private command results. A pure help parser and probe coordinator produce redacted JSON evidence. An internal authenticated API permits only configured device aliases. Motion execution is explicitly unavailable until the original package is imported and audited.

**Tech Stack:** Python 3.12+, standard library, FastAPI, Pydantic, Uvicorn, unittest, Docker.

**Spec:** docs/superpowers/specs/2026-09-15-duomove-runtime-design.md

## Global Constraints
- No device location, identity, provider, settings, permissions, power or sensor mutations.
- No arbitrary shell command interface; no local shell execution.
- Unknown capabilities remain unknown. Advertised syntax is not delivery verification.
- No repository secrets or real device endpoints; raw dumps remain internal to the probe.
- No public motion execution and no simulation fallback.
- Existing Node services, Supabase schemas and production devices remain unchanged.

---

### Task 1: Probe contract and transport
**Files:** duomove/probe.py; tests/test_probe.py
**Interface:** parse_location_help(text) -> dict; run_probe(serial, *, device_id, connect=False, runner=None) -> dict; execute(argv, timeout=8, max_bytes=262144) -> CommandResult.
- [x] Write tests for help-section scoping, vendor arguments, unknown/failed help, redaction and readiness gating.
- [x] Run `python -m unittest discover -s tests -v`; verify missing implementation fails.
- [x] Implement only fixed read-only commands and explicit optional ADB transport connection.
- [x] Run unit tests including real local child timeout/output-limit tests.

Acceptance example:
```python
flags = parse_location_help('set-test-provider-location gps --location LAT,LON\n  [--accuracy M]\nsend-extra-command gps COMMAND')['field_flags']
assert flags['lat_lon'] is True
assert flags['speed'] is False
```

### Task 2: Internal API and service configuration
**Files:** duomove/service.py; tests/test_service.py
**Interface:** Settings.from_env() -> Settings; create_app(settings=None, probe=None) -> FastAPI.
- [x] Write tests for missing/wrong authentication, alias validation, cooldown, single active probe, redacted errors and explicit motion refusal.
- [x] Verify failures before implementing service behavior.
- [x] Implement `/healthz`, `/v1/status`, `/v1/probes`, and an explicit 409 `/v1/motion` guard. No public docs endpoint.
- [x] Run all tests; verify protected routes do not invoke ADB on authentication failure.

Acceptance example:
```python
assert client.get('/healthz').status_code == 200
assert client.get('/v1/status').status_code == 401
assert client.post('/v1/motion', headers=auth).status_code == 409
```

### Task 3: CLI, packaging and deployment handoff
**Files:** duomove/__main__.py; Dockerfile; requirements.lock; requirements-dev.lock; .env.example; .gitignore; .dockerignore; README.md; docs/deployment.md; docs/verification.md; tests/test_cli.py
**Interface:** `python -m duomove probe --serial SERIAL [--connect]`; `python -m duomove serve`; `python -m duomove status`.
- [x] Write subprocess CLI tests for JSON output, missing ADB, invalid serials and rejected motion commands.
- [x] Verify failures, then implement exit codes and a runtime PORT-aware Uvicorn entrypoint.
- [x] Freeze the dependencies actually tested. Include a non-root Dockerfile with ADB; do not claim a Docker build without running one.
- [x] Run `python -m unittest discover -s tests -v` and `python -m compileall -q duomove tests`.
- [x] Test the HTTP service with a real local Uvicorn process.
- [x] Inspect all staged paths for secrets and generated files.
- [ ] Publish through the authorized GitHub connector to the feature branch and open a PR.

This phase does not depend on permission to access or move a live phone. Importing the missing original motion package and actual on-device verification are separate follow-on requirements, not silently successful steps.
