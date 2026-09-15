# DuoMove

Python runtime for the DuoPlus motion-service integration. **Current release: read-only diagnostics and an authenticated service bootstrap, not the completed motion orchestrator.**

The original `duoplus-motion` source has not been imported. This repository does not yet execute still/fidget/walk/drive/home, query WiGLE or OSRM, or write DuoPlus GPS/identity fields. It does not inject sensors. Motion requests fail explicitly; nothing falls back to simulation.

## What runs now

- A read-only ADB probe: transport state, Android release/SDK, location-command help and location-service diagnostics.
- A help parser that separates sample arguments from provider capability flags. For example, `--supportsSpeed` does not establish a sample `--speed` argument.
- A JSON Lines CLI and authenticated internal HTTP API.
- Fixed command allowlists, bounded subprocess output, timeouts, endpoint validation and raw-output redaction.
- A Dockerfile for a separate Railway Python service and CI for Python 3.12/3.13.

A successful probe reports available command syntax, **not** permission to inject locations or what Chrome/Maps observes. `location_delivery_verified` remains false.

## Run the CLI

Python 3.12+ on Linux or macOS. The probe itself uses only the Python standard library and requires a separately available `adb` executable. Its target must already allow your ADB connection. Nothing enables ADB, grants permissions, powers on devices or installs APKs.

```bash
python3 -m duomove status
python3 -m duomove probe --serial HOST:PORT --device-id lab-a --connect
```

Omit `--connect` for a transport already connected to the local ADB server. Exit codes: 0 = diagnostic collection complete, 1 = unavailable/partial diagnostics, 2 = invalid invocation/configuration, 130 = cancelled. `complete` does not mean location delivery was verified.

## Run the HTTP service

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
export DUOMOVE_SERVICE_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export DUOMOVE_ADB_TARGETS_JSON='{}'
python3 -m duomove serve
```

The service reads `PORT` (local default 8000), requires a token at startup, and does not automatically load `.env` files. Configure real device aliases in server environment variables, never in a browser request or commit.

| Route | Authentication | Behavior |
| --- | --- | --- |
| `GET /healthz` | None | HTTP liveness only; never claims fleet readiness. |
| `GET /v1/status` | Bearer token | Runtime scope and configured aliases; no endpoint addresses or secrets. |
| `POST /v1/probes` | Bearer token | Body: `{"device_id":"lab-a"}`. Only preconfigured aliases are accepted. |
| `POST /v1/motion` | Bearer token | Returns 409 `motion_executor_not_integrated`. |

Use the token only from an authorized server-side client. One probe may run at a time with a 30-second per-alias cooldown in a single service process. This is not multi-tenant authentication or a distributed fleet lock. No HTTP docs UI or raw dumps are exposed.

## Verify

```bash
pip install -r requirements-dev.lock
python3 -m unittest discover -s tests -v
python3 -m compileall -q duomove tests
```

Tests use synthetic command outputs and local subprocesses; they do not contact a live phone or consume provider quota. See [verification](docs/verification.md) for checks actually performed, and [deployment](docs/deployment.md) for Railway configuration.

## Approved next integration

Keep the existing Node controller responsible for scheduling, subscriptions, RPA coordination and device ownership. Run the existing Python motion package directly in this service after its actual source is available and audited. Enforce one location writer per device, shared provider pacing, durable receipts and explicit cancellation/reconciliation before enabling live motion. `DUOPLUS_REST` is the planned default; ADB writer modes remain disabled until separately verified.

Do not allow the new service and an existing controller to independently move the same device. Do not rotate hardware/subscriber identities as part of routine GPS updates. Modeled altitude/speed/bearing must never be labeled as delivered through the latitude/longitude-only REST adapter.

No changes are made to `stakeout-stations`, its database, or its deployed workers by this repository.
