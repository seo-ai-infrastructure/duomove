# DuoMove Site Fix — isolated getter test

This builds **two separate debug APKs**: `app` is the dplus module; `checker` is our own test app. It is not a system GPS writer. No listener, URLs, GMS targeting, native hook or sensor injection. Both manifests request no permissions, including no INTERNET permission.

## Build

From the repository root, use your uploaded vendor ZIP:

```bash
python3 tools/prepare_dplus_kit.py /path/to/dplus_demo.zip
cd android/site-fix
java -version   # JDK 21
./gradlew --no-daemon :core:fixtureTest :app:assembleDebug :checker:assembleDebug
```

Install SDK Platform 34 and Build Tools 34.0.0 first. The Java-only variant needs no NDK/CMake. The helper copies only hash-verified bridge/wrapper files, not native code or vendor build caches. Outputs:

- `app/build/outputs/apk/debug/app-debug.apk` — module, applicationId `com.example.dplus_demo`, dplus name `site_fix`.
- `checker/build/outputs/apk/debug/checker-debug.apk` — `net.stakeout.duomove.checker`.

`com.android.dp.Entry` and `init(Application)` are preserved. The module has no launcher activity; it is loaded using `dplus install`, not Android's ordinary app installer.

## Controlled device test (not executed by this publication)

Use one authorized test phone with ADB already connected. Set DEVICE to its current verified ADB serial. Every command below is pinned to that serial.

```bash
adb -s "$DEVICE" shell 'command -v dplus'
adb -s "$DEVICE" shell dplus dump
```

An empty module list does not prove the injector is missing. Inspect command errors and later installation/init evidence. A command not found is not proof that an otherwise unrelated device feature is available or unavailable outside PATH.

The supplied stock demo APK can be installed separately following the vendor instructions. It targets Settings and contains both HashMap and native openat demonstrations; use only a test device and unload it afterward. It is not necessary to leave that demo loaded to test this module.

Install the new checker and load the new module:

```bash
adb -s "$DEVICE" install -r checker/build/outputs/apk/debug/checker-debug.apk
adb -s "$DEVICE" push app/build/outputs/apk/debug/app-debug.apk /sdcard/Download/site_fix.apk
# If the vendor demo is currently installed, unload it first:
adb -s "$DEVICE" shell dplus uninstall dplus_demo
adb -s "$DEVICE" shell dplus install patch:/sdcard/Download/site_fix.apk
adb -s "$DEVICE" shell dplus dump
adb -s "$DEVICE" shell am force-stop net.stakeout.duomove.checker
adb -s "$DEVICE" shell am start -n net.stakeout.duomove.checker/.MainActivity
```

Stop on an installation/load error; do not infer success from a subsequent command. The checker displays SYNTHETIC GETTER TEST, creates one Location per second with original coordinates 0,0, and marks its own test objects mock on API 31+. The module does not change that marker.

From the repository root, first validate without writing:

```bash
python3 tools/publish_fixture.py --sample android/site-fix/sample.json --serial "$DEVICE"
# Explicit test-file write (not GPS/provider configuration):
python3 tools/publish_fixture.py --sample android/site-fix/sample.json --serial "$DEVICE" --publish
adb -s "$DEVICE" logcat -d -s site_fix:I duomove_checker:I '*:S'
```

The sample altitude is **illustrative**, not a verified elevation for those coordinates. The publisher supplies `issued_at_ms` using the device's clock. Do not add it to sample.json. The default TTL is 10 seconds. Increase `sequence` on every new sample, or `generation` for a new test run. Reusing the same sequence with a new timestamp is rejected by the running module. The sample expires; a one-time write is not a forever-running route.

The file is `files/duomove/fix.json` relative to the checker's private app directory. No `/sdcard/duoplus-motion` permission is needed. `run-as` must work for the debug checker; stop if the image denies it. It does not grant access to other apps.

`file_readback_verified` means exact bytes were read back. It does NOT mean dplus loaded, getters changed, a real GPS fix arrived, or any target app transmitted a payload. Confirm both the `site_fix` activation state and the checker's displayed getter values.

## Cleanup

```bash
adb -s "$DEVICE" shell run-as net.stakeout.duomove.checker rm -f files/duomove/fix.json
adb -s "$DEVICE" shell dplus uninstall site_fix
adb -s "$DEVICE" shell am force-stop net.stakeout.duomove.checker
```

Restart the checker to verify baseline values. Unloading a module should not be assumed to unhook an already running process; the force-stop/restart boundary matters. The file-only publisher never installs/uninstalls modules or stops apps automatically.

## Limitations

This is a bounded getter overlay, not a full Location/FLP replacement. Original timestamps, provider, mock flag, parcel data and internal fields remain original. Per-object snapshots prevent ordinary mixed-version getter groups; reused objects do not continuously track newer files. Expiry/removal can still cross a getter batch. No distributed ownership or durable run state exists in this test tool. The actual motion engine and real-device verification remain separate work.

See `../../docs/site-fix-kit-audit.md` for source checksums, implementation decisions and actual verification scope.
