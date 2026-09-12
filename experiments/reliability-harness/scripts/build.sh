#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLASS_DIR="$HARNESS_ROOT/build/classes"
SOURCE_LIST="$HARNESS_ROOT/build/sources.list"

mkdir -p "$CLASS_DIR"
rg --files "$HARNESS_ROOT/src" -g '*.java' | LC_ALL=C sort > "$SOURCE_LIST"

if command -v javac >/dev/null 2>&1; then
  javac -Xlint:all -Werror -d "$CLASS_DIR" @"$SOURCE_LIST"
elif java --list-modules 2>/dev/null | rg -q '^jdk.compiler@'; then
  java -m jdk.compiler/com.sun.tools.javac.Main \
    -Xlint:all -Werror -d "$CLASS_DIR" @"$SOURCE_LIST"
else
  echo 'BUILD_RESULT=ENVIRONMENT_BLOCKED'
  echo 'BUILD_REASON=JDK_COMPILER_UNAVAILABLE'
  exit 2
fi

java -cp "$CLASS_DIR" org.alvorada.reliability.AudioMarker \
  "$HARNESS_ROOT/build/audio-marker.wav"
echo 'BUILD_RESULT=PASS'

