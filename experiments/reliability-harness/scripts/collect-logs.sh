#!/usr/bin/env bash
set -euo pipefail

SERIAL="${ANDROID_SERIAL:-}"
if ! command -v adb >/dev/null 2>&1 || [[ -z "$SERIAL" ]]; then
  echo 'COLLECT_RESULT=ENVIRONMENT_BLOCKED'
  echo 'COLLECT_REASON=ADB_OR_ANDROID_SERIAL_UNAVAILABLE'
  exit 2
fi

adb -s "$SERIAL" logcat -d -v epoch ALVORADA_HARNESS:V '*:S'

