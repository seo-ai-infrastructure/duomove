# DuoMove

Python runtime foundation for a Railway-hosted DuoPlus motion service.

**Current release: read-only Android capability probe.** This is not yet the full fleet/motion controller. The original `duoplus-motion/` source was not located in the repository or available source searches; it has NOT been rewritten, imported, or executed here. No TypeScript port and no sensor injection.

## Included now

- Fixed ADB reads for Android release/SDK, `cmd location -h`, and `dumpsys location`.
- Tri-state advertised field support: true, false, or unknown (`null`). Provider declarations such as `--supportsSpeed` never imply that a location command accepts `--speed`.
- JSON reports distinguishing advertised syntax from verified writes. No report claims that GPS, speed, altitude or sensors were actually injected.
- Internal authenticated FastAPI service, configured device aliases, one probe at a time, and no arbitrary shell execution endpoint.
- CLI, unit/integration tests, Dockerfile and Railway configuration.

## Local use

Python 3.12 or newer. The parse/probe CLI uses the standard library; the HTTP service needs the pinned dependencies.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m duomove --help
```

Parse a saved command help file without contacting a device:

```bash
python -m duomove parse-help < location-help.txt
```

Run the probe only after ADB is enabled, authorized, connected, and the image-to-serial mapping is checked independently:

```bash
python -m duomove probe \
  --device-id test-phone \
  --serial "$ADB_SERIAL" \
  --output probe-report.json
```

The probe reads four fixed commands. It does not run `adb connect`, turn on a phone, enable ADB, install an APK, set appops, create a test provider, change GPS, or alter identities. ADB may start its local host daemon. CLI exit 0 means all diagnostic reads succeeded; exit 2 means partial/failed/unknown results. Neither means an injection succeeded.

Reports omit serials, raw dumpsys/help content and raw errors. Optional report files are mode 0600 and never overwrite existing files. `dumpsys_captured` means the command returned nonempty output, not that an app-visible location was parsed or verified.

## Railway configuration

The Dockerfile installs ADB and runs the Python HTTP service as a non-root user. `railway.toml` specifies one replica and `/healthz`. No live device jobs run on startup.

Set these through Railway Variables, not Git:

- `DUOMOVE_INTERNAL_TOKEN`: a high-entropy server-to-server secret of at least 32 characters.
- `DUOMOVE_TARGETS_JSON`: a JSON object mapping non-sensitive aliases to already connected ADB serials. `{}` disables all targets.
- `DUOMOVE_ADB_TIMEOUT_SECONDS`: 0.1–30, default 10 per command.

Example format only: `{"test-phone":"emulator-5554"}`. This is NOT an actual DuoPlus device mapping. `.env` is not loaded automatically. On a fresh Railway container, a configured serial alone does not establish an ADB connection; connection provisioning and provider whitelist checks remain separate, unimplemented setup work.

Prefer Railway private networking for calls from the control plane. This API is a single trusted-operator boundary, NOT multi-tenant browser authentication. Do not expose the internal token to Vercel client code.

```bash
python -m duomove serve  # honors PORT; default 8000
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS -H "Authorization: Bearer $DUOMOVE_INTERNAL_TOKEN" \
  http://127.0.0.1:8000/v1/status
curl -sS -X POST -H "Authorization: Bearer $DUOMOVE_INTERNAL_TOKEN" \
  http://127.0.0.1:8000/v1/probes/test-phone
```

The POST accepts no body, host, serial, command or credential. It returns 200 for a complete diagnostic report; 502 for partial/failed diagnostic reads; 401 without valid authorization; 404 for an unknown alias; 409 while another probe is running; 503 when the internal token is unconfigured. `/healthz` means process health, NOT device connectivity or fleet readiness.

## Tests

```bash
python -m pip install -r requirements.lock
python -m pip install -e '.[test]'
pytest -q
python -m compileall -q src tests
```

Tests use synthetic outputs and fake local ADB executables. No test connects to a real phone. See [verification.md](docs/verification.md) for the actual completed checks and outstanding checks.

## What remains before motion execution

1. Import and inspect the original `duoplus-motion/` source (not just its description).
2. Integrate its Python entrypoint with the existing Node control plane and durable Supabase records.
3. Implement shared location ownership, request pacing, cancellation, stale-command suppression and restart reconciliation across all writers. The diagnostic lock in this release is not that location lease.
4. Verify a real Android 15 capability report, then implement capability-gated writers. REST stays the default; ADB test/helper writers remain disabled. Full-location mock testing is not genuine GNSS.
5. Verify station profiles, WiGLE cache/selection, environment application and still/fidget/walk/drive/home commands before enabling live execution.

No Railway deployment, phone connection, provider API request, APK installation, or live-location update is performed by this repository publication.

## Reference contracts

- AOSP location shell source: https://android.googlesource.com/platform/frameworks/base/+/main/services/core/java/com/android/server/location/LocationShellCommand.java
- Android Location API: https://developer.android.com/reference/android/location/Location
- Python subprocess behavior: https://docs.python.org/3/library/subprocess.html
- Railway Dockerfiles: https://docs.railway.com/builds/dockerfiles
- Railway config: https://docs.railway.com/config-as-code/reference

Always use the actual device's help output to determine advertised syntax. Public AOSP syntax is not evidence of the configuration, privileges or behavior of a particular DuoPlus image.
