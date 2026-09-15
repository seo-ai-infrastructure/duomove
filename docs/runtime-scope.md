# DuoMove runtime scope

DuoMove runs Python directly on Railway. Existing Node scheduling remains the control plane; Python is the motion execution plane. No TypeScript port and no sensor injection.

## First milestone

- Runnable Python package and command-line interface with structured JSON output.
- Read-only Android capability probe: Android release/SDK, `cmd location -h`, and `dumpsys location`.
- Report supported shell flags from the set-test-provider-location command only; provider capability declarations are not proof of writable fields.
- No APK installation, mock-provider creation, GPS change, power action, or identity change during probing.
- Docker/Railway packaging and automated tests.
- Preserve a clean interface for the original duoplus-motion package; its source must be available and inspected before claiming it is integrated.

## Subsequent execution requirements

One location authority per device/run; external ownership acknowledgement; durable state; cancellation; sequence/generation checks; stale-sample suppression; and separate requested/provider-accepted/device-observed records. DuoPlus REST remains the default coordinate writer. ADB writers remain disabled until separately implemented and verified.

WiGLE data is a geographic reference, not proof of actual reception. Speed, bearing, accuracy and elevation remain model-only unless a verified writer supplies them. Live device actions require explicit configuration; failure must never silently fall back to simulation.

No live device actions or production deployment are authorized by the capability-probe step.
