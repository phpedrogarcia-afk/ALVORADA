#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo 'usage: generate-evidence-summary.sh <deterministic.log> <property.log>' >&2
  exit 64
fi

DETERMINISTIC="$(rg -o '^E0_SUMMARY=.*' "$1" | tail -n 1 | sed 's/^E0_SUMMARY=//')"
PROPERTY="$(rg -o '^E0_SUMMARY=.*' "$2" | tail -n 1 | sed 's/^E0_SUMMARY=//')"
if [[ -z "$DETERMINISTIC" || -z "$PROPERTY" ]]; then
  echo 'SUMMARY_RESULT=INVALID_INPUT' >&2
  exit 2
fi

printf '{"schema_version":1,"deterministic":%s,"property":%s}\n' \
  "$DETERMINISTIC" "$PROPERTY"

