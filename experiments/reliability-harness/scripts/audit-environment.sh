#!/usr/bin/env bash
set -euo pipefail

value_or_unavailable() {
  local executable="$1"
  shift
  if command -v "$executable" >/dev/null 2>&1; then
    "$executable" "$@" 2>&1 | head -n 1
  else
    echo 'UNAVAILABLE'
  fi
}

SDK_PATH="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"

echo "audit_timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "host_os=$(source /etc/os-release && echo "$PRETTY_NAME")"
echo "host_kernel=$(uname -srmo)"
echo "host_arch=$(uname -m)"
echo "container=$(if command -v systemd-detect-virt >/dev/null 2>&1; then systemd-detect-virt 2>/dev/null || echo none; elif [[ -f /.dockerenv ]]; then echo docker; else echo unknown; fi)"
echo "cpu_virtualization=$(lscpu 2>/dev/null | awk -F: '/^Virtualization:/ {gsub(/^[ \t]+/, "", $2); print $2}' || true)"
echo "jdk_runtime=$(java -version 2>&1 | head -n 1 || echo UNAVAILABLE)"
echo "javac_launcher=$(value_or_unavailable javac -version)"
echo "jdk_compiler_module=$(java -m jdk.compiler/com.sun.tools.javac.Main -version 2>&1 | head -n 1 || echo UNAVAILABLE)"
echo "gradle=$(value_or_unavailable gradle --version)"
echo "android_sdk_root=${SDK_PATH:-UNSET}"
echo "build_tools=$(if [[ -n "$SDK_PATH" && -d "$SDK_PATH/build-tools" ]]; then find "$SDK_PATH/build-tools" -mindepth 1 -maxdepth 1 -type d -printf '%f ' | LC_ALL=C sort; else echo UNAVAILABLE; fi)"
echo "platform_tools=$(if [[ -n "$SDK_PATH" && -d "$SDK_PATH/platform-tools" ]]; then echo AVAILABLE; else echo UNAVAILABLE; fi)"
echo "sdkmanager=$(value_or_unavailable sdkmanager --version)"
echo "avdmanager=$(value_or_unavailable avdmanager list avd)"
echo "adb=$(value_or_unavailable adb version)"
echo "emulator=$(value_or_unavailable emulator -version)"
echo "kvm_device=$(if [[ -c /dev/kvm ]]; then echo AVAILABLE; else echo UNAVAILABLE; fi)"
echo "disk_workspace=$(df -hP . | tail -n 1 | tr -s ' ')"

if command -v sdkmanager >/dev/null 2>&1; then
  echo 'installed_sdk_packages_begin'
  sdkmanager --list_installed 2>&1 || true
  echo 'installed_sdk_packages_end'
else
  echo 'installed_sdk_packages=UNAVAILABLE'
fi

if command -v emulator >/dev/null 2>&1; then
  echo 'available_avds_begin'
  emulator -list-avds 2>&1 || true
  echo 'available_avds_end'
else
  echo 'available_avds=UNAVAILABLE'
fi
