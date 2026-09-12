#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="${1:-}"

"$SCRIPT_DIR/build.sh"

if [[ -n "$OUTPUT_DIR" ]]; then
  mkdir -p "$OUTPUT_DIR"
  java -ea -cp "$HARNESS_ROOT/build/classes" \
    org.alvorada.reliability.E0TestRunner --suite=deterministic \
    | tee "$OUTPUT_DIR/deterministic.log"
  java -ea -cp "$HARNESS_ROOT/build/classes" \
    org.alvorada.reliability.E0TestRunner --suite=property \
    | tee "$OUTPUT_DIR/property.log"
else
  java -ea -cp "$HARNESS_ROOT/build/classes" \
    org.alvorada.reliability.E0TestRunner --suite=deterministic
  java -ea -cp "$HARNESS_ROOT/build/classes" \
    org.alvorada.reliability.E0TestRunner --suite=property
fi

echo 'E0_RESULT=PASS'

