# DuoMove phase 1: read-only diagnostics

## Approved target architecture
A separate Railway Python service hosts the existing duoplus-motion execution package. The existing Node control plane retains scheduling, subscription capacity, ownership and RPA coordination. One location authority per device. No TypeScript port, IMU injection, automatic identity fabrication, or simultaneous REST/mock-location writers.

## Current source boundary
The source baseline contains a README and runtime-scope documentation, but no Python implementation. A search of connected repository code and available Library files did not locate the original duoplus-motion package. Its pasted command examples are not its source. This change therefore implements the independently useful, approved read-only ADB probe and a Python service bootstrap. It does not substitute a newly invented motion engine or execute an unaudited CLI.

## Implemented scope
Python 3.12+; a standard-library diagnostic CLI and an authenticated FastAPI service. The probe runs get-state, the Android release and SDK getprops, cmd location -h, and dumpsys location. An explicit connection option may establish ADB transport; no authorization, settings, power, provider or coordinate changes are attempted. Commands are fixed, arguments are validated, subprocess execution does not use a local shell, output is bounded, and timeouts terminate the child. Raw dumps and endpoint addresses are not returned by the API.

The parser inspects only the set-test-provider-location help section. Provider property flags such as --supportsSpeed do not establish a --speed sample argument. Unavailable or unrecognized help produces unknown field flags, not invented support. Even a recognized flag is only advertised syntax; mock permission and location delivery remain unverified.

The HTTP API requires a deployment token of 32-256 URL-safe characters. Callers select a server-configured device alias, never arbitrary shell commands or host addresses. One active probe and a 30-second per-alias cooldown bound work in one process. This is an internal single-operator service, not tenant authentication or a distributed device lease. Missing/invalid authentication configuration fails closed. Motion requests fail explicitly; there is no simulation fallback.

## Deployment and validation
Provide a Dockerfile containing Python and ADB and read PORT at runtime. Keep the existing applications and live fleet untouched. Test parser behavior, missing ADB, unauthorized/offline devices, timeout/output limits, authentication, alias enforcement and no-write behavior. Docker and an actual phone must be verified separately. No live phone access is needed to run unit tests.

## Next integration boundary
Import and audit the real duoplus-motion source before implementing the executor. Coordinate a shared device lease and credential-wide rate gate with the Node controller before any live writes. Add durable Supabase receipts, cancellations and reconciliation before enabling motion. ADB helper mode stays disabled pending a separately verified APK.
