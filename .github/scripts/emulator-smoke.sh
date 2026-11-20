#!/usr/bin/env bash
set -Eeuo pipefail

SERIAL="${ANDROID_SERIAL:-emulator-5554}"
PACKAGE="com.jassim.ai"
ACTIVITY="$PACKAGE/.MainActivity"
APK="$GITHUB_WORKSPACE/.ci-artifacts/jassim-debug.apk"

dump_diagnostics() {
  echo "::group::Android emulator diagnostics"
  adb devices -l || true
  adb -s "$SERIAL" shell getprop sys.boot_completed || true
  adb -s "$SERIAL" logcat -b crash -d -v threadtime || true
  adb -s "$SERIAL" logcat -d -v threadtime -s AndroidRuntime ActivityManager ActivityTaskManager System.err || true
  adb -s "$SERIAL" shell dumpsys package "$PACKAGE" || true
  adb -s "$SERIAL" shell dumpsys activity activities | tail -n 120 || true
  echo "::endgroup::"
}

fail() {
  echo "::error::$1"
  dump_diagnostics
  exit 1
}

echo "Workspace: $GITHUB_WORKSPACE"
echo "Working directory: $PWD"
echo "APK path: $APK"

[[ -s "$APK" ]] || fail "Staged APK is missing or empty: $APK"
adb devices -l
state="$(adb -s "$SERIAL" get-state 2>&1)" || fail "Emulator is not available: $state"
[[ "$state" == "device" ]] || fail "Unexpected ADB state: $state"

booted="$(adb -s "$SERIAL" shell getprop sys.boot_completed | tr -d '\r')"
[[ "$booted" == "1" ]] || fail "Emulator has not completed boot (sys.boot_completed=$booted)"

adb -s "$SERIAL" install -r "$APK" || fail "APK installation failed"
adb -s "$SERIAL" shell am force-stop "$PACKAGE"
adb -s "$SERIAL" logcat -c

# am start -W may time out on a slow headless emulator. Capture its result,
# then independently require both a live process and the expected foreground activity.
set +e
start_output="$(adb -s "$SERIAL" shell am start -W -n "$ACTIVITY" 2>&1)"
start_status=$?
set -e
printf '%s\n' "$start_output"
echo "am start exit status: $start_status"

process=""
for attempt in $(seq 1 30); do
  process="$(adb -s "$SERIAL" shell pidof "$PACKAGE" 2>/dev/null | tr -d '\r' || true)"
  [[ -n "$process" ]] && break
  sleep 1
done
[[ -n "$process" ]] || fail "JASSIM process did not stay alive after MainActivity launch"

resumed=""
for attempt in $(seq 1 15); do
  resumed="$(adb -s "$SERIAL" shell dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity' | tail -n 1 | tr -d '\r' || true)"
  if printf '%s' "$resumed" | grep -Fq "$ACTIVITY"; then
    break
  fi
  sleep 1
done
printf 'Resumed activity: %s\n' "$resumed"
printf '%s' "$resumed" | grep -Fq "$ACTIVITY" || fail "MainActivity is not the resumed foreground activity"

echo "ANDROID_EMULATOR_SMOKE_OK: APK installed, MainActivity foregrounded, and process alive ($process)"
