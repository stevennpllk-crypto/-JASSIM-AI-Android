#!/usr/bin/env bash
set -u

OUT="${RUNNER_TEMP:-/tmp}/jassim-emulator-diagnostics.txt"
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
  (adb version || true)
  (adb devices -l || true)
  echo
  echo "=== Emulator / ADB processes ==="
  (pgrep -af 'emulator|qemu|adb' || true)
  echo
  echo "=== Android SDK / AVD environment ==="
  env | sort | grep -E '^(ANDROID|JAVA_HOME|RUNNER_TEMP|HOME)=' || true
  echo
  echo "=== Recent emulator / adb log files ==="
  find "${RUNNER_TEMP:-/tmp}" "$HOME/.android" -maxdepth 5 -type f \\( -iname '*emulator*.log' -o -iname '*adb*.log' \\) -print 2>/dev/null | head -n 30 | while IFS= read -r file; do
    echo "--- $file"
    tail -n 100 "$file" 2>/dev/null || true
  done
  echo
  echo "=== Device boot property (best effort) ==="
  adb -s emulator-5554 shell getprop sys.boot_completed 2>&1 || true
} 2>&1 | tee "$OUT"

echo "Diagnostics saved to: $OUT"
