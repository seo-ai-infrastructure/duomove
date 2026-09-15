# Dplus kit audit and checker-only implementation — 2026-09-15

## Uploaded inputs inspected

| Input | SHA-256 |
|---|---|
| dplus_demo.zip | abbb84ac746d82a1c00ab2a38b1d431d640451afae0df98b5c57c0f51811c06f |
| dplus_demo (1).apk | 831117a75f2b303a551c12104aaa162a84e33761911252c31f071fddab2c8dbb |
| dpbridge.jar inside ZIP | b23fd0b42ae82a46e58a8e5581ce1fb39dffc2b64003f6f88efc936959741099 |

The ZIP and APK both contain an assets/config.json targeting com.android.settings, with name dplus_demo, package com.example.dplus_demo, ishook true, and libs libdplus_demo.so. This verifies their inspected configuration, not byte-for-byte source/APK equivalence or APK safety/signing provenance.

ZIP Entry.java is com.android.dp.Entry with init(Application). javap on the actual dpbridge.jar confirms LSPHelpers.findAndHookMethod overloads, LSP_MethodH.MethodHookParam.setResult/hasThrowable, Unhook.unhook, and DPLog.i.

The uploaded native-lib.cpp actively installs an openat hook in JNI_OnLoad and logs file paths. It is not an inert library. The new module omits libs and native build entirely. The original supplied binaries are unchanged.

The kit includes .idea, .gradle, local.properties and build debris. None are copied into the new source project. Public source uses only checksum-verified build inputs retrieved from the supplied ZIP or the vendor's documented URL; no vendor binaries are committed.

## Implemented boundary

A standalone Java-only test module, retaining com.android.dp.Entry and applicationId com.example.dplus_demo. Config targets only the included net.stakeout.duomove.checker, with an additional exact runtime package check. No listener, network endpoint, native injection, mock-flag alteration or sensor injection.

The checker constructs synthetic Location objects. A live GNSS fix is not required to test getter interception. This does not establish Chrome/Maps/FLP observations. If an unrelated app never obtains or constructs a Location, getter hooks do not deliver one for it.

Files use the checker-private files/duomove/fix.json, not arbitrary /sdcard JSON. Publication uses authorized ADB run-as against the debuggable checker, a unique temporary file, atomic rename, and exact readback. No all-files permission, root, appops change or production app data access is requested. Device shell/run-as behavior still needs validation on an actual image.

The core validates numeric type, finite values, ranges, WGS84 ellipsoidal altitude labeling, optional fields, freshness, and generation/sequence order. Repeated file reads do not extend expiry. A maximum 500ms refresh delay is intentional. Epoch time is supplied from the device by the publisher; remaining TTL is also limited by device monotonic time after load. Clock anomalies or unavailable files cause original values to pass through.

One immutable snapshot is bound by object identity to each Location (up to 512 live weak references). New observations should use new Location objects, as the included checker does. An already-bound cached object does NOT become a live moving location. Bound values expire and revert to original values. This avoids normal per-field sample mixing but is not a transactional guarantee across arbitrary getter calls that span expiry/removal. It does not alter parceling, internal fields, distanceTo, toString, getTime, getElapsedRealtimeNanos, getProvider or isMock. Those may describe original state. This is explicitly a getter test, not a coherent replacement of every Android Location operation.

Optional presence methods match fixture fields. Unsupported speed/bearing uncertainty and MSL altitude are not carried over from the original object. Original getter exceptions are not suppressed. Hook installation failure attempts to unhook earlier registrations and reports failure.

Generation/sequence protection is in process only; no persistent replay protection, distributed location lease or fleet recovery is claimed. Use one operator/publisher and a dedicated checker device. This source does not replace the missing Python motion orchestrator.

## Tests run locally

- 27 Java core assertions passed on OpenJDK 21 (Java 8 source target).
- 13 Python unittest tests passed, including core Java invocation, validation, explicit-write gate, error/readback handling and a real local shell test of argument quoting and atomic 0600 file publication.
- Python compileall passed.
- Android SDK/Gradle downloads are unavailable in the local container. CI is configured to build the real APKs; its results must be checked separately.
- No phone installation, dplus module load, runtime hook result or Railway deployment has been performed.

## Sources consulted

DuoPlus module SDK/build/install: https://help.duoplus.net/docs/How-to-develop-plugin-modules
Android Location optional fields, datum and clocks: https://developer.android.com/reference/android/location/Location
Android storage restrictions: https://developer.android.com/about/versions/11/privacy/storage
App-private files: https://developer.android.com/training/data-storage/app-specific
ADB command transport: https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/client/commandline.cpp
