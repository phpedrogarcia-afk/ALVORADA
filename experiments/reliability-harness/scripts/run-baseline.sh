#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ARTIFACT_DIR="${1:-$HARNESS_ROOT/build/baseline}"

mkdir -p "$ARTIFACT_DIR"
"$SCRIPT_DIR/audit-environment.sh" | tee "$ARTIFACT_DIR/environment-audit.log"
"$SCRIPT_DIR/test-e0.sh" "$ARTIFACT_DIR/e0"
"$SCRIPT_DIR/generate-evidence-summary.sh" \
  "$ARTIFACT_DIR/e0/deterministic.log" "$ARTIFACT_DIR/e0/property.log" \
  | tee "$ARTIFACT_DIR/e0-summary.json"

E1_BLOCKED=0
for API in 31 34 35 36 37; do
  if ! "$SCRIPT_DIR/provision-avd.sh" --api "$API" \
      | tee "$ARTIFACT_DIR/e1-api-${API}-preflight.log"; then
    E1_BLOCKED=1
  fi
done

if [[ "$E1_BLOCKED" -eq 1 ]]; then
  echo 'BASELINE_RESULT=E0_PASS/E1_CONDITIONAL'
else
  echo 'BASELINE_RESULT=E0_PASS/E1_READY_FOR_SCENARIO_EXECUTION'
fi
