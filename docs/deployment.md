# Railway diagnostic-service deployment

## Scope
This release deploys diagnostics only. It does not deploy a motion executor, Redis queue, Supabase schema or UI. The original Python motion package is not present. Do not connect production movement jobs to this release.

## Service configuration
Use a new service sourced from this repository after reviewing the feature branch. Keep existing services unchanged. Railway detects the root `Dockerfile`; use its default start command, which reads `PORT` in Python. Configure `/healthz` as the deployment healthcheck path and use one replica. Use Railway private networking for the existing Node control plane where possible; never expose ADB's server port 5037 publicly.

Required variable: `DUOMOVE_SERVICE_TOKEN`, a fresh 32-256-character URL-safe secret. Generate it locally with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Never commit the token or place it in a `NEXT_PUBLIC_` variable.

Optional variables:
- `DUOMOVE_ADB_TARGETS_JSON`: an object mapping non-sensitive aliases to authorized ADB serials or DNS/IPv4 `host:port` targets. Default `{}`.
- `DUOMOVE_ADB_CONNECT`: `true` to explicitly establish transport before each requested probe; default `false`.
- `DUOMOVE_ADB_TIMEOUT_SECONDS`: per-command deadline, 1-30 seconds; default 8.
- `PORT`: supplied by Railway; default 8000 locally.

No provider API keys or Supabase service keys are needed for this phase. The service does not enable a device's ADB access, add network whitelist entries, or approve debugging keys. A device that has not authorized the connection returns unavailable, not success. Configure target access separately using the provider's supported controls before an authorized test.

Raw `dumpsys location` output is never returned or persisted by this service. Summaries include hashes and status only. Detailed actual app location readback is a separate observation feature, not something the help parser can prove.

## Checks after deployment
1. `/healthz` returns HTTP 200 with `scope=http_service_only` and `motion_enabled=false`.
2. `/v1/status` without the bearer token returns 401.
3. `/v1/status` with the token returns `mode=diagnostics_only`.
4. An authorized `/v1/motion` request returns 409, not fake successful movement.
5. After adding a designated test-device alias, run one `/v1/probes` request and inspect the resulting `status`, check failures and advertised argument flags. Do not label this a full-location delivery test.

Do not enable multiple replicas as a workaround for cooldowns. The current semaphore and cooldown are process-local. Distributed ownership, provider-wide rate gates and Supabase history are later integration work.

## Local Docker check
```bash
docker build -t duomove .
docker run --rm duomove python -m duomove status
docker run --rm duomove adb version
# Pass DUOMOVE_SERVICE_TOKEN from the existing shell environment, not a literal.
docker run --rm -p 8000:8000 -e DUOMOVE_SERVICE_TOKEN duomove
```

The image and ADB packages are not digest-pinned; the exact Python application dependencies are pinned to the tested environment. This is not a claim of bit-for-bit reproducible OS packages.

## Official references checked for this implementation
- AOSP LocationShellCommand: https://android.googlesource.com/platform/frameworks/base/+/main/services/core/java/com/android/server/location/LocationShellCommand.java
- Railway Dockerfile detection: https://docs.railway.com/builds/dockerfiles
- Railway PORT and startup healthchecks: https://docs.railway.com/deployments/healthchecks
- Railway Docker start behavior: https://docs.railway.com/builds/build-and-start-commands
- FastAPI bearer authentication: https://fastapi.tiangolo.com/reference/security/

The actual phone's help output remains the probe input; upstream source is not substituted for on-device evidence. No `railway.toml` is included: deployment settings are described here rather than depending on legacy Config as Code behavior for a new service.
