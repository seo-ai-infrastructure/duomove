# DuoMove first milestone: read-only capability probe

Approved architecture: Railway executes Python directly; Node remains the scheduler/control plane. No sensor injection. This milestone implements the read-only probe and deployment packaging, not the missing original motion package. Never represent a newly generated implementation as the original duoplus-motion source.

Core reads: getprop release, getprop SDK, cmd location -h, dumpsys location. Every device command is a fixed argv tuple, pinned to an explicit serial; no shell interpolation, installs, appops, mock providers, GPS writes, power actions, connect/disconnect, or identity changes. ADB must already be authorized and connected. The local adb daemon may start automatically; no handset configuration is written.

Help parsing is scoped strictly to the set-test-provider-location synopsis. --supportsSpeed on add-test-provider is not --speed. Unreadable/unknown help yields null field support, not false success. Advertised syntax is not runtime permission, injection success, or device-observed location. Report all four command outcomes and sanitized metadata; never expose dumpsys content, coordinates, endpoint addresses, or authorization data over HTTP.

FastAPI runs one Uvicorn worker. Internal bearer authentication and configured device aliases are required for POST /v1/probes/{device_id}; no request can supply a host, shell, executable path, or credentials. Missing configuration fails closed. A single in-process probe lock returns 409 for overlap; it is not the future fleet/location lease. /healthz indicates process health only. Protected /v1/status reports readiness separately. An offline CLI parser is clearly labeled offline_help, never a live device observation.

CLI core requires only Python standard library. API dependencies pinned to the installed versions exercised in local tests. Docker target Python 3.12; local interpreter version is reported separately. No real device connection or Railway deployment during this repository milestone.
