#!/usr/bin/env bash
set -euo pipefail

MODE='audit'
PROPOSAL_PATH=''

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="${2:-audit}"; shift 2 ;;
    --audit) MODE='audit'; shift ;;
    --dry-run) MODE='dry-run'; shift ;;
    --apply) MODE='apply'; shift ;;
    --proposal) PROPOSAL_PATH="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$HARNESS_DIR/../.." && pwd)"

if [ -z "$PROPOSAL_PATH" ]; then
  PROPOSAL_PATH="$REPO_ROOT/evidence/g1/raw-mission05r/canonical_catalog_proposal.json"
fi

echo "WAVE1_PROVISIONING_PROBE=STARTED"
echo "API36=NOT_PROVISIONED"
echo "SYSTEM_IMAGE=NOT_PROVISIONED"
echo "AVD=NOT_CREATED"
echo "P1_P10=UNKNOWN"
echo "READY_FOR_E1_WAVE1=NO"
echo "wave1_mode=$MODE"
echo "wave1_timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "proposal_path=$PROPOSAL_PATH"

if [ ! -f "$PROPOSAL_PATH" ]; then
  echo "WAVE1_STATUS=FAIL"
  echo "FAILURE_REASON=PROPOSAL_FILE_NOT_FOUND"
  exit 2
fi

# 1. Cryptographic Pre-flight Contract Verification
echo "WAVE1_PREFLIGHT_CHECK=BEGIN"
ENFORCE_FLAG=""
if [ "$MODE" = "apply" ] || [ "$MODE" = "dry-run" ]; then
  ENFORCE_FLAG="--enforce-approval"
fi

set +e
preflight_output=$(python3 "$SCRIPT_DIR/catalog_discovery.py" wave1-preflight --proposal "$PROPOSAL_PATH" $ENFORCE_FLAG 2>&1)
preflight_exit_code=$?
set -e

printf '%s\n' "$preflight_output"
echo "WAVE1_PREFLIGHT_EXIT_CODE=$preflight_exit_code"

if [ $preflight_exit_code -ne 0 ]; then
  echo "WAVE1_STATUS=BLOCKED_BY_PREFLIGHT"
  if echo "$preflight_output" | grep -q "LOCK_NOT_APPROVED_BY_FOUNDER"; then
    echo "WAVE1_BLOCKER=LOCK_NOT_APPROVED_BY_FOUNDER"
  else
    echo "WAVE1_BLOCKER=PREFLIGHT_INTEGRITY_VIOLATION"
  fi
  exit $preflight_exit_code
fi

# Extract packages to install from preflight output
install_pkgs=$(echo "$preflight_output" | awk -F'=' '/^WAVE1_INSTALL_PACKAGES=/ {print $2}')
echo "RESOLVED_INSTALL_PACKAGES=$install_pkgs"

# 2. Environment & Tooling Verification
android_home_raw="${ANDROID_HOME:-}"
android_sdk_root_raw="${ANDROID_SDK_ROOT:-}"
canonical_sdk_root=""

if [ -n "$android_home_raw" ] && [ -d "$android_home_raw" ]; then
  canonical_sdk_root="$(realpath -e -- "$android_home_raw" 2>/dev/null || true)"
elif [ -n "$android_sdk_root_raw" ] && [ -d "$android_sdk_root_raw" ]; then
  canonical_sdk_root="$(realpath -e -- "$android_sdk_root_raw" 2>/dev/null || true)"
fi

sdkmanager_location="NOT_FOUND"
if [ -n "$canonical_sdk_root" ] && [ -x "$canonical_sdk_root/cmdline-tools/latest/bin/sdkmanager" ]; then
  sdkmanager_location="$canonical_sdk_root/cmdline-tools/latest/bin/sdkmanager"
elif [ -n "$canonical_sdk_root" ] && [ -d "$canonical_sdk_root/cmdline-tools" ]; then
  for candidate in "$canonical_sdk_root"/cmdline-tools/*/bin/sdkmanager; do
    if [ -f "$candidate" ] && [ -x "$candidate" ]; then
      sdkmanager_location="$candidate"
      break
    fi
  done
elif command -v sdkmanager >/dev/null 2>&1; then
  sdkmanager_location="$(command -v sdkmanager)"
fi

echo "CANONICAL_SDK_ROOT=${canonical_sdk_root:-NOT_RESOLVED}"
echo "SDKMANAGER_LOCATION=$sdkmanager_location"

if [ "$MODE" = "audit" ] || [ "$MODE" = "dry-run" ]; then
  echo "WAVE1_STATUS=PREFLIGHT_PLAN_VERIFIED"
  echo "WAVE1_ACTION=NO_PACKAGES_INSTALLED_DRY_RUN_OR_AUDIT"
  echo "API36=NOT_PROVISIONED"
  echo "SYSTEM_IMAGE=NOT_PROVISIONED"
  echo "AVD=NOT_CREATED"
  echo "P1_P10=UNKNOWN"
  echo "READY_FOR_E1_WAVE1=NO"
  echo "WAVE1_PROVISIONING_PROBE=COMPLETE"
  exit 0
fi

# 3. Apply Mode (Only reachable when lock is approved by founder)
if [ "$MODE" = "apply" ]; then
  if [ "$sdkmanager_location" = "NOT_FOUND" ]; then
    echo "WAVE1_STATUS=FAIL"
    echo "FAILURE_REASON=SDKMANAGER_NOT_FOUND"
    exit 2
  fi

  echo "WAVE1_PACKAGE_MUTATION=BEGIN"
  "$sdkmanager_location" --sdk_root="$canonical_sdk_root" $install_pkgs </dev/null
  install_exit_code=$?
  echo "WAVE1_PACKAGE_MUTATION_EXIT_CODE=$install_exit_code"

  if [ $install_exit_code -ne 0 ]; then
    echo "WAVE1_STATUS=PACKAGE_INSTALLATION_FAILED"
    exit $install_exit_code
  fi

  echo "WAVE1_STATUS=PACKAGES_PROVISIONED"
  echo "READY_FOR_E1_WAVE1=YES"
fi

echo "AVD=NOT_CREATED"
echo "P1_P10=UNKNOWN"
echo "WAVE1_PROVISIONING_PROBE=COMPLETE"
exit 0
