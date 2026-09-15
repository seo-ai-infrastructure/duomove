# Verification record — 15 September 2026

## Completed locally

Environment: Linux, CPython 3.13.5. No real device addresses or provider credentials were configured.

- `PYTHONPATH=src pytest -q`: **53 passed**.
- `python -m compileall -q src tests`: passed.
- `setuptools.build_meta.build_wheel(...)`: built `duomove-0.1.0-py3-none-any.whl` using the installed build backend.
- Real local Uvicorn subprocess: startup, `/healthz` 200, unauthenticated `/v1/status` 401, authenticated `/v1/status` 200, and graceful SIGTERM shutdown passed. Uvicorn may re-raise SIGTERM after cleanup; the smoke check accepts exit 0 or termination by SIGTERM only after its shutdown-complete message.
- The protected status explicitly reports `original_motion_source_integrated=false` and `motion_execution_enabled=false`.
- Tests cover fixed command selection, argument validation, timeout and partial failures, advertised-capability parsing, raw-output omission, authentication, target allowlisting, concurrent request rejection, and private non-overwriting report files.
- Parser/runner tests were run before implementation and failed for missing features; service/CLI tests were also run before implementation. Subsequent runs passed.

## Not verified locally

- Python 3.12 execution and fresh dependency installation: the local environment is Python 3.13 and cannot resolve external hosts.
- Docker image build/run: Docker is not installed in the local environment. CI is configured to test it.
- GitHub Actions result: check the pull request checks; this record does not pre-claim CI success.
- Railway deployment, private networking, ADB connection provisioning or provider-side IP authorization.
- A real DuoPlus Android 15 device: no ADB executable or connected phone was present locally. Synthetic test outputs are not device evidence.
- No full motion engine, WiGLE lookup, DuoPlus REST write, ADB test-provider write, helper APK, Redis lease or Supabase persistence was exercised. Those features are not implemented in this milestone.

## Review boundaries

Only four fixed device read commands exist. HTTP callers supply a configured alias, never shell text or an endpoint. Reports exclude raw help/dumpsys/error output and device serials. `/healthz` is process health only. The service-level diagnostic lock is not a distributed device/location lease.

The original `duoplus-motion/` source is still required for its direct Python integration. No package with that name was recovered or silently replaced.
