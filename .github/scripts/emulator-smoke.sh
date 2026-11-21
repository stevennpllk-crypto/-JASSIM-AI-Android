#!/usr/bin/env bash
set -Eeuo pipefail

SERIAL="${ANDROID_SERIAL:-emulator-5554}"
PACKAGE="com.jassim.ai"
ACTIVITY="$PACKAGE/.MainActivity"
APK="$GITHUB_WORKSPACE/app/build/outputs/apk/debug/app-debug.apk"

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

[[ -s "$APK" ]] || fail "Debug APK is missing or empty: $APK"
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

# Assert the native Android UI exposes the account-memory entry point.
adb -s "$SERIAL" shell uiautomator dump /sdcard/jassim-window.xml >/dev/null 2>&1 || fail "Could not inspect Android UI hierarchy"
ui_hierarchy="$(adb -s "$SERIAL" shell cat /sdcard/jassim-window.xml 2>/dev/null || true)"
printf '%s' "$ui_hierarchy" | grep -Fq 'إدارة ذاكرة حسابك' || fail "Account memory button is missing from the Android UI"

# Guard against exporting the placeholder captured before the assistant response streamed.
MAIN_ACTIVITY="$GITHUB_WORKSPACE/app/src/main/java/com/jassim/ai/MainActivity.java"
grep -Fq 'String currentText = bubble.getText().toString();' "$MAIN_ACTIVITY" || fail "Assistant long-press handler does not read the live bubble text"
grep -Fq 'saveAssistantMessageAsFile(currentText);' "$MAIN_ACTIVITY" || fail "Assistant TXT export is not wired to the live response"
REPLY_EXPORT="$GITHUB_WORKSPACE/app/src/main/java/com/jassim/ai/ReplyExport.java"
grep -Fq 'output.write(ReplyExport.toUtf8(content));' "$MAIN_ACTIVITY" || fail "TXT export is not wired to the UTF-8 helper"
grep -Fq 'return content.getBytes(StandardCharsets.UTF_8);' "$REPLY_EXPORT" || fail "ReplyExport helper does not encode content as UTF-8"
echo "TXT_EXPORT_REGRESSION_GUARD_OK: live response text is used and UTF-8 export is wired"

echo "ANDROID_EMULATOR_SMOKE_OK: APK installed, MainActivity foregrounded, process alive ($process), and account-memory control is visible"
