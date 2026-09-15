# Verification record — 2026-09-15

## Checks completed locally

- Runtime: Python 3.13.5 on Linux.
- `python3 -m unittest discover -s tests -v`: 37 tests passed, no failures.
- Red/green sequence: 15 probe tests, 16 service tests and 6 CLI tests each failed before their implementation, then passed after implementation.
- `python3 -m compileall -q duomove tests`: passed.
- `python3 -m duomove status`: diagnostic-only scope, motion disabled.
- Real local Uvicorn HTTP process: five checks passed (healthcheck 200, unauthenticated status 401, authenticated diagnostic status 200, unknown alias 404, motion refusal 409).
- Timeout/output-limit tests used real local Python child processes. Device-facing tests used synthetic ADB output; no device or provider was contacted.

## Not verified in this environment

- Docker build: not run; Docker is unavailable locally. A CI container-build job is supplied, but its result must be checked independently.
- Python 3.12 execution: not run locally. CI includes Python 3.12 and 3.13 jobs.
- Railway deployment, ADB reachability, Android 15 image behavior, mock authorization, actual app-observed location and provider write acceptance: not tested.
- Original `duoplus-motion` code integration, motion scheduling, WiGLE/OSRM and live location writers: not implemented in this milestone.
- Multi-tenant authorization, distributed leases, Supabase persistence and restart recovery: not implemented in this milestone.

No live device location, identity, power, permission, provider or sensor settings were changed. A successful diagnostic HTTP healthcheck is not a successful fleet deployment or verified Android location delivery.
