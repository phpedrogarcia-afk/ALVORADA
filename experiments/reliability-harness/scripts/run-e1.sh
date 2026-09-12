#!/usr/bin/env bash
set -euo pipefail

API=''
SCENARIO=''
STRATEGY=''
REPEAT='3'

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api) API="${2:-}"; shift 2 ;;
    --scenario) SCENARIO="${2:-}"; shift 2 ;;
    --strategy) STRATEGY="${2:-}"; shift 2 ;;
    --repeat) REPEAT="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done

if [[ ! "$API" =~ ^(31|34|35|36|37)$ ]] \
  || [[ -z "$SCENARIO" ]] \
  || [[ ! "$STRATEGY" =~ ^(ALARM_CLOCK|EXACT_ALLOW_IDLE)$ ]] \
  || [[ ! "$REPEAT" =~ ^[1-9][0-9]*$ ]]; then
  echo 'usage: run-e1.sh --api {31|34|35|36|37} --scenario NAME --strategy {ALARM_CLOCK|EXACT_ALLOW_IDLE} --repeat N' >&2
  exit 64
fi

SUPPORTED_SCENARIOS='NORMAL_FOREGROUND NORMAL_BACKGROUND SCREEN_OFF LOCKED DOZE APP_STANDBY ORDINARY_PROCESS_DEATH REBOOT_UNLOCK REBOOT_NO_FIRST_UNLOCK TIME_FORWARD TIME_BACKWARD TIMEZONE_CHANGE EXACT_CAPABILITY_AVAILABLE EXACT_CAPABILITY_UNAVAILABLE NOTIFICATIONS_ENABLED NOTIFICATIONS_DISABLED FSI_AVAILABLE FSI_UNAVAILABLE SNOOZE DISMISS TWO_CLOSE_ALARMS OFFLINE OPTIONAL_SERVICES_ABSENT FORCE_STOP'
if ! tr ' ' '\n' <<< "$SUPPORTED_SCENARIOS" | rg -Fxq "$SCENARIO"; then
  echo 'E1_RESULT=NOT_TESTABLE'
  echo 'E1_REASON=UNKNOWN_SCENARIO'
  exit 3
fi

for executable in adb emulator; do
  if ! command -v "$executable" >/dev/null 2>&1; then
    echo 'E1_RESULT=ENVIRONMENT_BLOCKED'
    echo "E1_REASON=${executable^^}_UNAVAILABLE"
    echo "API=$API"
    echo "SCENARIO=$SCENARIO"
    echo "SCHEDULING_STRATEGY=$STRATEGY"
    exit 2
  fi
done

SERIAL="${ANDROID_SERIAL:-}"
if [[ -z "$SERIAL" ]]; then
  echo 'E1_RESULT=ENVIRONMENT_BLOCKED'
  echo 'E1_REASON=ANDROID_SERIAL_UNSET'
  exit 2
fi

DEVICE_API="$(adb -s "$SERIAL" shell getprop ro.build.version.sdk 2>/dev/null | tr -d '\r')"
if [[ "$DEVICE_API" != "$API" ]]; then
  echo 'E1_RESULT=ENVIRONMENT_BLOCKED'
  echo "E1_REASON=DEVICE_API_MISMATCH_EXPECTED_${API}_ACTUAL_${DEVICE_API:-UNKNOWN}"
  exit 2
fi

# A future Android adapter must expose this test-only broadcast contract. This
# version intentionally refuses to fabricate an adapter result.
PACKAGE='org.alvorada.reliability.harness'
if ! adb -s "$SERIAL" shell pm path "$PACKAGE" 2>/dev/null | rg -q '^package:'; then
  echo 'E1_RESULT=ENVIRONMENT_BLOCKED'
  echo 'E1_REASON=ANDROID_ADAPTER_NOT_INSTALLED'
  echo "API=$API"
  echo "SCENARIO=$SCENARIO"
  echo "SCHEDULING_STRATEGY=$STRATEGY"
  exit 2
fi

echo 'E1_RESULT=NOT_TESTABLE'
echo 'E1_REASON=ANDROID_ADAPTER_PROTOCOL_NOT_IMPLEMENTED_IN_HARNESS_0_1_0'
echo 'NOTE=No ADB command was sent; no scenario was counted as executed.'
exit 3

