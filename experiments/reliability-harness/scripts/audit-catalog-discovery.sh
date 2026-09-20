#!/usr/bin/env bash
set -euo pipefail

MODE='local'
if [[ "${1:-}" == '--ci' ]]; then
  MODE='ci'
elif [[ $# -ne 0 ]]; then
  echo 'usage: audit-catalog-discovery.sh [--ci]' >&2
  exit 64
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "CATALOG_DISCOVERY_PROBE=STARTED"
echo "API36=NOT_PROVISIONED"
echo "SYSTEM_IMAGE=NOT_PROVISIONED"
echo "AVD=NOT_CREATED"
echo "P1_P10=UNKNOWN"
echo "READY_FOR_E1_WAVE1=NO"
echo "LOCK_APPROVED=NO"
echo "audit_mode=$MODE"
echo "audit_timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "github_actions=${GITHUB_ACTIONS:-false}"
echo "github_sha=${GITHUB_SHA:-UNSET}"
echo "github_run_id=${GITHUB_RUN_ID:-UNSET}"

# 1. Static Policy Self-Verification
echo "STATIC_POLICY_CHECK=BEGIN"
python3 "$SCRIPT_DIR/catalog_discovery.py" verify-script "$SCRIPT_DIR/audit-catalog-discovery.sh"
echo "STATIC_POLICY_CHECK=PASS"

# 2. Automated Test Suite Pre-check
echo "CATALOG_ENGINE_UNIT_TESTS=BEGIN"
python3 -m unittest discover -s "$SCRIPT_DIR" -p "test_*.py"
echo "CATALOG_ENGINE_UNIT_TESTS=PASS"

# 3. Locate Android SDK & sdkmanager
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

if [ "$sdkmanager_location" = "NOT_FOUND" ]; then
  if [ "$MODE" = "local" ]; then
    echo "CATALOG_DISCOVERY_STATUS=LOCAL_SKIPPED_NO_SDKMANAGER"
    echo "API36=NOT_PROVISIONED"
    echo "SYSTEM_IMAGE=NOT_PROVISIONED"
    echo "AVD=NOT_CREATED"
    echo "P1_P10=UNKNOWN"
    echo "READY_FOR_E1_WAVE1=NO"
    echo "CATALOG_DISCOVERY_PROBE=COMPLETE"
    exit 0
  fi
  echo "CATALOG_DISCOVERY_STATUS=FAIL"
  echo "FAILURE_REASON=SDKMANAGER_NOT_FOUND"
  exit 2
fi

# 4. Read-Only Catalog Query (channel 0 = stable)
raw_catalog_file="$HARNESS_DIR/raw_sdk_catalog.txt"
proposal_file="$HARNESS_DIR/canonical_catalog_proposal.json"

echo "SDKMANAGER_CATALOG_QUERY=BEGIN"
set +e
"$sdkmanager_location" --list --verbose --channel=0 > "$raw_catalog_file" 2>&1
query_exit_code=$?
set -e
echo "SDKMANAGER_CATALOG_QUERY_EXIT_CODE=$query_exit_code"

if [ $query_exit_code -ne 0 ]; then
  echo "CATALOG_DISCOVERY_STATUS=FAIL"
  echo "FAILURE_REASON=SDKMANAGER_LIST_COMMAND_FAILED"
  exit $query_exit_code
fi

# 5. Parse and Canonicalize via CatalogParser
echo "CATALOG_PARSING_AND_CANONICALIZATION=BEGIN"
set +e
python3 "$SCRIPT_DIR/catalog_discovery.py" parse \
  --input "$raw_catalog_file" \
  --output "$proposal_file" \
  --repo-sha "${GITHUB_SHA:-LOCAL_PROBE}" \
  --run-id "${GITHUB_RUN_ID:-LOCAL_RUN}"
parse_exit_code=$?
set -e

echo "CATALOG_PARSE_EXIT_CODE=$parse_exit_code"
if [ $parse_exit_code -eq 0 ]; then
  echo "CATALOG_DISCOVERY_STATUS=PASS"
else
  echo "CATALOG_DISCOVERY_STATUS=CONDITIONAL"
fi

echo "API36=NOT_PROVISIONED"
echo "SYSTEM_IMAGE=NOT_PROVISIONED"
echo "AVD=NOT_CREATED"
echo "P1_P10=UNKNOWN"
echo "READY_FOR_E1_WAVE1=NO"
echo "CATALOG_DISCOVERY_PROBE=COMPLETE"
exit $parse_exit_code
