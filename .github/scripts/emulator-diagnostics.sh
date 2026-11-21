#!/usr/bin/env bash
set -u

OUT="${RUNNER_TEMP:-/tmp}/jassim-emulator-diagnostics.txt"
SDK_ADB="${ANDROID_HOME:-/usr/local/lib/android/sdk}/platform-tools/adb"
if [[ -x "$SDK_ADB" ]]; then
  ADB="$SDK_ADB"
elif command -v adb >/dev/null 2>&1; then
  ADB="$(command -v adb)"
else
  ADB=""
fi
mkdir -p "$(dirname "$OUT")"
{
  echo "=== JASSIM Android emulator diagnostics ==="
  date -u
  echo
  echo "=== Runner resources ==="
  (free -h || true)
  (df -h "${RUNNER_TEMP:-/tmp}" || true)
  echo
  echo "=== ADB version and devices ==="
  ([[ -n "$ADB" ]] && "$ADB" version || echo "ADB binary not found")
  ([[ -n "$ADB" ]] && "$ADB" devices -l || true)
  echo
  echo "=== Emulator / ADB processes ==="
  (pgrep -af 'emulator|qemu|adb' || true)
  echo
  echo "=== Android SDK / AVD environment ==="
  env | sort | grep -E '^(ANDROID|JAVA_HOME|RUNNER_TEMP|HOME)=' || true
  echo
  echo "=== Recent emulator / adb log files ==="
  find "${RUNNER_TEMP:-/tmp}" "$HOME/.android" -maxdepth 5 -type f \( -iname '*emulator*.log' -o -iname '*adb*.log' \) -print 2>/dev/null | head -n 30 | while IFS= read -r file; do
    echo "--- $file"
    tail -n 100 "$file" 2>/dev/null || true
  done
  echo
  echo "=== Device boot property (best effort) ==="
  if [[ -n "$ADB" ]] && "$ADB" -s emulator-5554 get-state >/dev/null 2>&1; then
    "$ADB" -s emulator-5554 shell getprop sys.boot_completed 2>&1 || true
  else
    echo "Emulator is no longer connected (it may have been shut down after the smoke test); skipping boot-property probe."
  fi
} 2>&1 | tee "$OUT"

echo "Diagnostics saved to: $OUT"
