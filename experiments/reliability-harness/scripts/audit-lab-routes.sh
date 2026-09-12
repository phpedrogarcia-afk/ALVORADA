#!/usr/bin/env bash
set -euo pipefail

MODE='local'
if [[ "${1:-}" == '--ci' ]]; then
  MODE='ci'
elif [[ $# -ne 0 ]]; then
  echo 'usage: audit-lab-routes.sh [--ci]' >&2
  exit 64
fi

available() {
  if command -v "$1" >/dev/null 2>&1; then
    printf 'AVAILABLE:%s' "$(command -v "$1")"
  else
    printf 'UNAVAILABLE'
  fi
}

first_line() {
  local executable="$1"
  shift
  if command -v "$executable" >/dev/null 2>&1; then
    "$executable" "$@" 2>&1 | head -n 1 || true
  else
    printf 'UNAVAILABLE\n'
  fi
}

yes_no() {
  if "$@"; then
    printf 'YES'
  else
    printf 'NO'
  fi
}

echo 'schema_version=2'
echo "audit_mode=$MODE"
echo "audit_timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "host_os=$(source /etc/os-release && printf '%s' "$PRETTY_NAME")"
echo "host_kernel=$(uname -srmo)"
echo "host_arch=$(uname -m)"
echo "cpu_count=$(getconf _NPROCESSORS_ONLN)"
echo "memory_kib=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
echo "workspace_disk=$(df -hP . | tail -n 1 | tr -s ' ')"
echo "github_actions=${GITHUB_ACTIONS:-false}"
echo "github_repository=${GITHUB_REPOSITORY:-UNSET}"
echo "github_sha=${GITHUB_SHA:-UNSET}"
echo "github_ref=${GITHUB_REF:-UNSET}"
echo "github_workflow=${GITHUB_WORKFLOW:-UNSET}"
echo "github_run_id=${GITHUB_RUN_ID:-UNSET}"
echo "github_run_attempt=${GITHUB_RUN_ATTEMPT:-UNSET}"
echo "github_job=${GITHUB_JOB:-UNSET}"
echo "runner_environment=${RUNNER_ENVIRONMENT:-UNSET}"
echo "runner_os=${RUNNER_OS:-UNSET}"
echo "runner_arch=${RUNNER_ARCH:-UNSET}"
echo "runner_image_os=${ImageOS:-UNSET}"
echo "runner_image_version=${ImageVersion:-UNSET}"
echo "repository_visibility=${ALVORADA_REPOSITORY_VISIBILITY:-UNSET}"
echo "declared_workflow_permissions=${ALVORADA_WORKFLOW_PERMISSIONS:-UNSET}"
echo "git=$(first_line git --version)"
echo "checked_out_commit=$(git rev-parse HEAD 2>/dev/null || printf 'UNAVAILABLE')"
echo "java=$(first_line java -version)"
echo "gradle=$(first_line gradle --version)"
echo "sdkmanager=$(available sdkmanager)"
echo "avdmanager=$(available avdmanager)"
echo "adb=$(available adb)"
echo "emulator=$(available emulator)"
echo "android_sdk_root=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-UNSET}}"
echo "dev_kvm=$(if [[ -c /dev/kvm ]]; then stat -c '%A:%U:%G:%t:%T' /dev/kvm; else printf 'UNAVAILABLE'; fi)"
echo "dev_kvm_readable=$(yes_no test -r /dev/kvm)"
echo "dev_kvm_writable=$(yes_no test -w /dev/kvm)"

echo 'network_begin'
echo "https_github_status=$(curl --silent --show-error --location --output /dev/null --write-out '%{http_code}' --max-time 15 https://github.com/ 2>&1 || true)"
echo "dns_github=$(getent ahosts github.com 2>/dev/null | awk 'NR == 1 {print $1}' || true)"
echo "default_route=$(ip route show default 2>/dev/null | sed -E 's/(via )[^ ]+/\1REDACTED/' | head -n 1 || true)"
echo 'network_end'

if command -v emulator >/dev/null 2>&1; then
  echo 'emulator_accel_check_begin'
  emulator -accel-check 2>&1 || true
  echo 'emulator_accel_check_end'
fi

if command -v sdkmanager >/dev/null 2>&1; then
  echo 'installed_sdk_packages_begin'
  sdkmanager --list_installed 2>&1 || true
  echo 'installed_sdk_packages_end'
  echo 'available_sdk_packages_begin'
  sdkmanager --list 2>&1 || true
  echo 'available_sdk_packages_end'
fi

if [[ "$MODE" == 'local' ]]; then
  echo "local_accelerated_available=$(if [[ -c /dev/kvm ]] && command -v emulator >/dev/null 2>&1; then printf 'YES'; else printf 'NO'; fi)"
  echo 'remote_accelerated_available=NO_CONFIGURED_ENDPOINT_OBSERVED'
  echo 'ci_accelerated_platform_capability=YES_GITHUB_HOSTED_LINUX_DOCUMENTED'
  echo 'ci_execution_binding=NO_AUTHORIZED_ALVORADA_REPOSITORY_OR_RUNNER'
  echo 'lab_route_result=LAB_BLOCKED'
  exit 2
fi

if [[ "${GITHUB_ACTIONS:-false}" != 'true' ]]; then
  echo 'lab_route_result=ENVIRONMENT_BLOCKED'
  echo 'lab_route_reason=CI_MODE_OUTSIDE_GITHUB_ACTIONS'
  exit 2
fi

KVM_AVAILABLE=NO
ANDROID_SDK_AVAILABLE=NO
EMULATOR_INSTALLABLE=NO
AVD_CREATION_POSSIBLE=NO

if [[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then
  KVM_AVAILABLE=YES
fi

sdk_listing=''
if command -v sdkmanager >/dev/null 2>&1; then
  ANDROID_SDK_AVAILABLE=YES
  sdk_listing="$(sdkmanager --list 2>/dev/null || true)"
fi

if command -v emulator >/dev/null 2>&1 || grep -Eq '^emulator[[:space:]]' <<<"$sdk_listing"; then
  EMULATOR_INSTALLABLE=YES
fi

if [[ "$KVM_AVAILABLE" == YES && "$ANDROID_SDK_AVAILABLE" == YES && "$EMULATOR_INSTALLABLE" == YES ]] \
  && command -v avdmanager >/dev/null 2>&1 \
  && grep -Fq 'system-images;android-36;' <<<"$sdk_listing"; then
  AVD_CREATION_POSSIBLE=YES
fi

echo "KVM_AVAILABLE=$KVM_AVAILABLE"
echo "ANDROID_SDK_AVAILABLE=$ANDROID_SDK_AVAILABLE"
echo "EMULATOR_INSTALLABLE=$EMULATOR_INSTALLABLE"
echo "AVD_CREATION_POSSIBLE=$AVD_CREATION_POSSIBLE"

if [[ "$KVM_AVAILABLE" != YES || "$ANDROID_SDK_AVAILABLE" != YES || "$EMULATOR_INSTALLABLE" != YES || "$AVD_CREATION_POSSIBLE" != YES ]]; then
  echo 'lab_route_result=LAB_DISCOVERY_CONDITIONAL'
  echo 'lab_route_reason=ONE_OR_MORE_REQUIRED_CAPABILITIES_NOT_PROVEN'
  exit 2
fi

echo 'lab_route_result=LAB_DISCOVERY_PASS'
echo 'note=This is route discovery only; it does not satisfy the ten E1 prechecks.'
