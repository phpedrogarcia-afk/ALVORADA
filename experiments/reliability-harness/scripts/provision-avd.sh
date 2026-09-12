#!/usr/bin/env bash
set -euo pipefail

API=''
MODE='check'
while [[ $# -gt 0 ]]; do
  case "$1" in
    --api) API="${2:-}"; shift 2 ;;
    --install) MODE='install'; shift ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done

if [[ ! "$API" =~ ^(31|34|35|36|37)$ ]]; then
  echo 'usage: provision-avd.sh --api {31|34|35|36|37} [--install]' >&2
  exit 64
fi

for executable in sdkmanager avdmanager emulator adb; do
  if ! command -v "$executable" >/dev/null 2>&1; then
    echo 'PROVISION_RESULT=ENVIRONMENT_BLOCKED'
    echo "PROVISION_REASON=${executable^^}_UNAVAILABLE"
    echo "API=$API"
    exit 2
  fi
done

PACKAGE="system-images;android-${API};google_apis;x86_64"
AVD="alvorada-g1-api-${API}"
if ! sdkmanager --list_installed 2>/dev/null | rg -Fq "$PACKAGE"; then
  if [[ "$MODE" != 'install' ]]; then
    echo 'PROVISION_RESULT=ENVIRONMENT_BLOCKED'
    echo 'PROVISION_REASON=SYSTEM_IMAGE_NOT_INSTALLED'
    echo "SYSTEM_IMAGE=$PACKAGE"
    exit 2
  fi
  sdkmanager "$PACKAGE"
fi

if ! emulator -list-avds | rg -Fxq "$AVD"; then
  echo 'no' | avdmanager create avd --name "$AVD" --package "$PACKAGE" --device pixel_5
fi

echo 'PROVISION_RESULT=READY'
echo "API=$API"
echo "SYSTEM_IMAGE=$PACKAGE"
echo "AVD=$AVD"
echo 'START_COMMAND_BEGIN'
echo "emulator -avd $AVD -no-window -no-audio -no-snapshot -wipe-data"
echo 'START_COMMAND_END'

