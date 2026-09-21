#!/usr/bin/env python3
"""
ALVORADA — Catalog Core Contracts & Static Policy Verifier
Contract Version: RECOVERY-G1-001-R1

Implements:
1. ALVORADA_CANONICAL_JSON_V1: Strict deterministic serialization, custom control-character
   escaping (\\u00xx lowercase hex for U+0000..U+001F), duplicate object key rejection,
   type guards (no float/NaN/Infinity), and SHA-256 hashing.
2. CatalogParser: Fail-closed parser strictly for the 5 HARD_LOCK packages
   producing deterministic projection without approval or lock generation.
3. CatalogReadOnlyPolicy: Static AST/regex verification lane and structural CLI invocation
   allowlists strictly enforcing read-only discovery, rejecting mutating system commands,
   positional sdkmanager package installations, AVD creation, and unauthorized emulator invocations.
"""

import argparse
import datetime
import hashlib
import json
import math
import os
import re
import shlex
import sys
from typing import Any, Dict, List, Optional, Tuple

# -----------------------------------------------------------------------------
# 1. ALVORADA_CANONICAL_JSON_V1 SPECIFICATION
# -----------------------------------------------------------------------------

CANONICAL_JSON_CONTRACT = "ALVORADA_CANONICAL_JSON_V1"

# IEEE 754 Safe Integer Domain [-(2**53 - 1), (2**53 - 1)]
MIN_SAFE_INTEGER = -9007199254740991
MAX_SAFE_INTEGER = 9007199254740991

ISO_8601_UTC_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def validate_canonical_timestamp(ts: str) -> None:
    """
    Enforces strict ISO-8601 UTC timestamp contract: YYYY-MM-DDTHH:MM:SSZ
    Fails closed if milliseconds, timezone offsets other than Z, or invalid
    calendar dates are provided.
    This validator is an explicit primitive for semantic timestamp fields,
    not an automatic heuristic for all string values.
    """
    if not isinstance(ts, str):
        raise TypeError(f"Timestamp must be a string, got {type(ts).__name__}")
    if not ISO_8601_UTC_REGEX.match(ts):
        raise ValueError(f"Timestamp does not conform to canonical format YYYY-MM-DDTHH:MM:SSZ: {ts!r}")
    try:
        datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as e:
        raise ValueError(f"Invalid calendar date/time in canonical timestamp: {ts!r}") from e


def escape_canonical_string(s: str) -> str:
    """
    Escapes a string strictly according to ALVORADA_CANONICAL_JSON_V1:
    - Control characters U+0000 through U+001F: \\u00xx with lowercase hex.
      (Short escapes like \\b, \\f, \\n, \\r, \\t are strictly prohibited in canonical form).
    - Quotation mark (U+0022): \\"
    - Reverse solidus / Backslash (U+005C): \\\\
    - Isolated surrogates (U+D800 to U+DFFF): rejected (raises ValueError).
    - All other Unicode characters: emitted directly as UTF-8 characters without
      implicit Unicode normalization.
    """
    out = ['"']
    for char in s:
        code = ord(char)
        if 0xD800 <= code <= 0xDFFF:
            raise ValueError(f"Isolated surrogate code point U+{code:04X} detected: {s!r}")
        elif code < 0x20:
            out.append(f"\\u{code:04x}")
        elif code == 0x22:  # '"'
            out.append('\\"')
        elif code == 0x5C:  # '\'
            out.append('\\\\')
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def serialize_canonical_json_v1(obj: Any) -> str:
    """
    Pure deterministic serializer for ALVORADA_CANONICAL_JSON_V1.
    - Dict keys sorted lexicographically by Unicode code point.
    - Separators strictly (',', ':') with no insignificant whitespace.
    - Strings escaped strictly via escape_canonical_string().
    """
    if isinstance(obj, bool):
        return "true" if obj else "false"
    elif isinstance(obj, int):
        return str(obj)
    elif isinstance(obj, float):
        raise ValueError(f"Floats are strictly forbidden in {CANONICAL_JSON_CONTRACT}: {obj}")
    elif isinstance(obj, str):
        return escape_canonical_string(obj)
    elif isinstance(obj, dict):
        items = []
        for k in sorted(obj.keys()):
            if not isinstance(k, str):
                raise TypeError(f"Dictionary keys must be strings, got {type(k).__name__}")
            escaped_k = escape_canonical_string(k)
            val_str = serialize_canonical_json_v1(obj[k])
            items.append(f"{escaped_k}:{val_str}")
        return "{" + ",".join(items) + "}"
    elif isinstance(obj, list):
        items = [serialize_canonical_json_v1(item) for item in obj]
        return "[" + ",".join(items) + "]"
    elif obj is None:
        return "null"
    elif isinstance(obj, set):
        raise TypeError(
            f"Sets are not permitted directly in {CANONICAL_JSON_CONTRACT} payload. "
            "Convert explicitly to a sorted array before canonicalization."
        )
    else:
        raise TypeError(f"Unsupported data type in {CANONICAL_JSON_CONTRACT}: {type(obj).__name__}")


def validate_canonical_data(obj: Any) -> Any:
    """
    Recursively validates and canonicalizes Python data structures:
    - Rejects floats, NaN, and Infinity unconditionally.
    - Enforces integer range [-9007199254740991, 9007199254740991].
    - Rejects isolated surrogate code points in strings and dictionary keys.
    - Rejects sets directly (must be explicitly converted to sorted list before).
    - Sorts dictionary keys lexicographically by Unicode code points.
    - Recursively processes nested lists and dicts.
    """
    if isinstance(obj, bool):
        return obj
    elif isinstance(obj, int):
        if obj < MIN_SAFE_INTEGER or obj > MAX_SAFE_INTEGER:
            raise ValueError(
                f"Integer {obj} out of safe domain [{MIN_SAFE_INTEGER}, {MAX_SAFE_INTEGER}]"
            )
        return obj
    elif isinstance(obj, float):
        raise ValueError(
            f"Floats (including NaN and Infinity) are strictly forbidden in {CANONICAL_JSON_CONTRACT}: {obj}"
        )
    elif isinstance(obj, str):
        for char in obj:
            code = ord(char)
            if 0xD800 <= code <= 0xDFFF:
                raise ValueError(
                    f"Isolated surrogate code point U+{code:04X} detected in string: {obj!r}"
                )
        return obj
    elif isinstance(obj, dict):
        validated_dict = {}
        for k in sorted(obj.keys()):
            if not isinstance(k, str):
                raise TypeError(f"Dictionary keys must be strings, got {type(k).__name__}")
            for char in k:
                code = ord(char)
                if 0xD800 <= code <= 0xDFFF:
                    raise ValueError(
                        f"Isolated surrogate code point U+{code:04X} detected in key: {k!r}"
                    )
            validated_dict[k] = validate_canonical_data(obj[k])
        return validated_dict
    elif isinstance(obj, list):
        return [validate_canonical_data(item) for item in obj]
    elif obj is None:
        return None
    elif isinstance(obj, set):
        raise TypeError(
            f"Sets are not permitted directly in {CANONICAL_JSON_CONTRACT} payload. "
            "Convert explicitly to a sorted array before canonicalization."
        )
    else:
        raise TypeError(
            f"Unsupported data type in {CANONICAL_JSON_CONTRACT}: {type(obj).__name__}"
        )


def canonicalize_json_v1(data: Any) -> bytes:
    """
    Serializes data to bytes according to ALVORADA_CANONICAL_JSON_V1:
    - Validates data types, integer domain, surrogate absence.
    - Serializes via pure deterministic serializer enforcing \\u00xx control escapes.
    - Encodes as UTF-8 without BOM.
    - Ensures no trailing newline in digested payload.
    """
    validated = validate_canonical_data(data)
    json_str = serialize_canonical_json_v1(validated)
    payload_bytes = json_str.encode("utf-8")
    if payload_bytes.startswith(b"\xef\xbb\xbf"):
        raise ValueError("Unexpected UTF-8 BOM detected in canonical output")
    if payload_bytes.endswith(b"\n") or payload_bytes.endswith(b"\r"):
        raise ValueError("Trailing newline detected in canonical payload")
    return payload_bytes


def hash_canonical_json_v1(data: Any) -> str:
    """Computes SHA-256 over ALVORADA_CANONICAL_JSON_V1 serialized payload."""
    raw_bytes = canonicalize_json_v1(data)
    return hashlib.sha256(raw_bytes).hexdigest()


def json_loads_canonical(json_str: str) -> Any:
    """
    Safely parses JSON string with strict fail-closed rejection of:
    - floats (including scientific notation)
    - NaN and Infinity constants
    - duplicate keys at root and nested levels (DUPLICATE_OBJECT_KEY)
    """
    def reject_float(s: str) -> None:
        raise ValueError(f"Floats are strictly forbidden in {CANONICAL_JSON_CONTRACT}: {s}")

    def reject_constant(c: str) -> None:
        raise ValueError(f"Special float constant {c!r} is strictly forbidden in {CANONICAL_JSON_CONTRACT}")

    def reject_duplicate_keys_hook(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        d = {}
        for key, val in pairs:
            if key in d:
                raise ValueError(f"DUPLICATE_OBJECT_KEY: Duplicate key {key!r} detected in JSON object")
            d[key] = val
        return d

    return json.loads(
        json_str,
        parse_float=reject_float,
        parse_constant=reject_constant,
        object_pairs_hook=reject_duplicate_keys_hook,
    )


# -----------------------------------------------------------------------------
# 2. CATALOG PARSER SPECIFICATION
# -----------------------------------------------------------------------------

HARD_LOCK_PACKAGES = [
    "emulator",
    "platform-tools",
    "platforms;android-36",
    "build-tools;36.0.0",
    "system-images;android-36;default;x86_64",
]

# The 6 mandatory package states mandated by MISSÃO AUTONOMY-RECOVERY-001 Section 6
PACKAGE_STATE_ABSENT = "ABSENT"
PACKAGE_STATE_PRESENT_MATCHING = "PRESENT_MATCHING_CATALOG"
PACKAGE_STATE_PRESENT_DIFFERENT = "PRESENT_DIFFERENT_REVISION"
PACKAGE_STATE_PARTIAL_OR_CORRUPT = "PARTIAL_OR_CORRUPT"
PACKAGE_STATE_CATALOG_MISSING = "CATALOG_ENTRY_MISSING"
PACKAGE_STATE_METADATA_AMBIGUOUS = "METADATA_AMBIGUOUS"

ALL_PACKAGE_STATES = {
    PACKAGE_STATE_ABSENT,
    PACKAGE_STATE_PRESENT_MATCHING,
    PACKAGE_STATE_PRESENT_DIFFERENT,
    PACKAGE_STATE_PARTIAL_OR_CORRUPT,
    PACKAGE_STATE_CATALOG_MISSING,
    PACKAGE_STATE_METADATA_AMBIGUOUS,
}


class CatalogParser:
    """
    Fail-closed parser for `sdkmanager --list --verbose --channel=0` output.
    Extracts installed and available revisions strictly for the 5 HARD_LOCK packages.
    Produces a pure projection dictionary without generating lock approval or lock digests.
    """

    def __init__(self, raw_output: str, metadata: Optional[Dict[str, str]] = None):
        self.raw_output = raw_output
        self.metadata = metadata or {}

    def parse(self) -> Dict[str, Any]:
        """
        Parses raw sdkmanager output and returns a projection dictionary.
        Catalog revision and installed revision are tracked independently.
        Fails closed on duplicate entries or corrupt metadata.
        """
        installed_entries: Dict[str, List[Dict[str, Any]]] = {}
        available_entries: Dict[str, List[Dict[str, Any]]] = {}

        current_section: Optional[str] = None
        current_pkg: Optional[str] = None
        current_entry: Optional[Dict[str, Any]] = None

        def finalize_entry() -> None:
            nonlocal current_pkg, current_entry, current_section
            if current_pkg and current_entry is not None:
                version = current_entry.get("version")
                if not version or not version.strip():
                    current_entry["is_corrupt"] = True
                else:
                    current_entry["version"] = version.strip()
                    current_entry["is_corrupt"] = False

                if current_section == "installed":
                    installed_entries.setdefault(current_pkg, []).append(current_entry)
                elif current_section == "available":
                    available_entries.setdefault(current_pkg, []).append(current_entry)
            current_pkg = None
            current_entry = None

        for line in self.raw_output.splitlines():
            line_stripped = line.strip()

            if "Installed packages:" in line:
                finalize_entry()
                current_section = "installed"
                continue
            elif "Available Packages:" in line or "Available Updates:" in line:
                finalize_entry()
                current_section = "available"
                continue

            if current_section is None or not line_stripped or line_stripped.startswith("---"):
                continue

            # A package identifier line begins at column 0 (no leading whitespace)
            if not line.startswith(" ") and not line.startswith("\t"):
                finalize_entry()
                parts = line_stripped.split()
                if parts:
                    current_pkg = parts[0]
                    current_entry = {"version": None, "raw_lines": [line_stripped]}
                continue

            # Under the current package header, properties are indented
            if current_pkg and current_entry is not None:
                current_entry["raw_lines"].append(line_stripped)
                if line_stripped.startswith("Version:"):
                    vparts = line_stripped.split(":", 1)
                    if len(vparts) == 2:
                        current_entry["version"] = vparts[1].strip()

        finalize_entry()

        packages_list = []
        is_complete = True
        has_ambiguity = False

        for pkg in HARD_LOCK_PACKAGES:
            inst_list = installed_entries.get(pkg, [])
            avail_list = available_entries.get(pkg, [])

            # Check for corruption in any parsed entry for this package
            corrupt = any(e.get("is_corrupt") for e in inst_list) or any(e.get("is_corrupt") for e in avail_list)
            if corrupt:
                state = PACKAGE_STATE_PARTIAL_OR_CORRUPT
                is_complete = False
                packages_list.append({
                    "catalog_revision": None,
                    "error": "CORRUPT_OR_MISSING_VERSION_FIELD",
                    "installed_revision": None,
                    "package_path": pkg,
                    "state": state,
                })
                continue

            # Check for ambiguity (duplicate entries in installed or available)
            if len(inst_list) > 1 or len(avail_list) > 1:
                state = PACKAGE_STATE_METADATA_AMBIGUOUS
                has_ambiguity = True
                is_complete = False
                packages_list.append({
                    "catalog_revision": None,
                    "error": "DUPLICATE_ENTRIES_DETECTED",
                    "installed_revision": None,
                    "package_path": pkg,
                    "state": state,
                })
                continue

            inst_rev = inst_list[0]["version"] if inst_list else None
            avail_rev = avail_list[0]["version"] if avail_list else None

            if avail_rev is None and inst_rev is None:
                state = PACKAGE_STATE_CATALOG_MISSING
                is_complete = False
            elif avail_rev is None and inst_rev is not None:
                state = PACKAGE_STATE_CATALOG_MISSING
                is_complete = False
            elif inst_rev is None:
                state = PACKAGE_STATE_ABSENT
            elif inst_rev == avail_rev:
                state = PACKAGE_STATE_PRESENT_MATCHING
            else:
                state = PACKAGE_STATE_PRESENT_DIFFERENT

            packages_list.append({
                "catalog_revision": avail_rev,
                "installed_revision": inst_rev,
                "package_path": pkg,
                "state": state,
            })

        # Explicitly sort packages array by package_path
        packages_sorted = sorted(packages_list, key=lambda p: p["package_path"])

        projection: Dict[str, Any] = {
            "contract": "ALVORADA_CATALOG_PROJECTION_V1",
            "has_ambiguity": has_ambiguity,
            "is_complete": is_complete,
            "packages": packages_sorted,
        }
        if self.metadata:
            projection["metadata"] = dict(sorted(self.metadata.items()))

        return projection


# -----------------------------------------------------------------------------
# 3. CATALOG READ-ONLY STATIC POLICY VERIFIER & STRUCTURAL ALLOWLISTS
# -----------------------------------------------------------------------------

def _make_cmd_pattern(cmd_regex: str) -> str:
    """Builds regex matching a command with optional path, extension, and quotes."""
    return rf'(?:^|[;&|`\s\(\)])["\']?(?:[\w./\\:-]*[/\\:])?{cmd_regex}(?:\.exe|\.bat)?["\']?(?:$|[;&|`\s\(\)])'


class CatalogReadOnlyPolicy:
    """
    CLAIM ENVELOPE:
    This verifier provides:
    1. Static AST/regex policy filtering targeting dangerous mutating commands.
    2. Dedicated structural argument allowlists for sdkmanager and emulator CLI invocations.

    Allowlist Constraints:
    - sdkmanager: Allowed ONLY with exact read-only flags:
        --sdk_root=<value> (mandatory, exactly one)
        --list (mandatory, exactly one)
        --verbose (mandatory, exactly one)
        --channel=0 (mandatory, exactly one)
      Zero positional arguments, zero package names, zero mutating flags.
    - emulator: Allowed ONLY with:
        ["-help"]
        ["-help-gpu"] (ONLY if help_proved_gpu is empirically established).
    - Prohibited tools: sudo, apt, apt-get, curl, wget, setfacl, chmod 777, yes |,
      avdmanager create, adb install.

    It handles whitespace variations, absolute paths, quoted arguments, and line continuations.
    It does NOT claim complete security against arbitrary adversarial shell obfuscation
    (such as eval, base64 decoding, variable substitution, or custom binary wrappers).
    All execution must additionally be constrained by OS-level sandbox and unprivileged runner.
    """

    PROHIBITED_TOOL_PATTERNS = [
        (_make_cmd_pattern(r"sudo"), "SUDO_PROHIBITED"),
        (_make_cmd_pattern(r"apt(?:-get)?"), "APT_PROHIBITED"),
        (_make_cmd_pattern(r"curl"), "CURL_PROHIBITED"),
        (_make_cmd_pattern(r"wget"), "WGET_PROHIBITED"),
        (_make_cmd_pattern(r"setfacl"), "SETFACL_PROHIBITED"),
    ]

    PROHIBITED_SPECIFIC_PATTERNS = [
        (
            rf'(?:^|[;&|`\s\(\)])["\']?(?:[\w./\\:-]*[/\\:])?chmod(?:\.exe)?["\']?\s+(?:-[a-zA-Z0-9]+\s+)*["\']?777["\']?',
            "CHMOD_777_PROHIBITED",
        ),
        (
            rf'(?:^|[;&|`\s\(\)])["\']?(?:[\w./\\:-]*[/\\:])?yes(?:\.exe)?["\']?\s*\|',
            "YES_PIPE_PROHIBITED",
        ),
        (
            rf'(?:^|[;&|`\s\(\)])["\']?(?:[\w./\\:-]*[/\\:])?avdmanager(?:\.bat)?(?:\.exe)?["\']?\s+.*?["\']?create["\']?',
            "AVD_CREATE_PROHIBITED",
        ),
        (
            rf'(?:^|[;&|`\s\(\)])["\']?(?:[\w./\\:-]*[/\\:])?adb(?:\.exe)?["\']?\s+.*?["\']?install["\']?',
            "ADB_INSTALL_PROHIBITED",
        ),
        (
            r'["\']?--(?:install|update|uninstall|licenses)["\']?',
            "SDK_MUTATION_PROHIBITED",
        ),
        (
            rf'(?:^|[;&|`\s\(\)])["\']?(?:[\w./\\:-]*[/\\:])?emulator(?:\.exe)?["\']?\s+.*?(-avd|@\w+)',
            "EMULATOR_AVD_PROHIBITED",
        ),
    ]

    def verify_sdkmanager_invocation(self, args: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Structural allowlist verification for sdkmanager invocation.
        Permits ONLY:
        - --sdk_root=<value> (or --sdk_root <value>) [mandatory, exactly one]
        - --list [mandatory, exactly one]
        - --verbose [mandatory, exactly one]
        - --channel=0 (or --channel 0) [mandatory, exactly one]
        Rejects any positional arguments (packages), unknown flags, or repeated flags.
        """
        has_sdk_root = False
        has_list = False
        has_verbose = False
        has_channel_0 = False

        i = 0
        while i < len(args):
            raw_arg = args[i].strip()
            if not raw_arg:
                i += 1
                continue

            # Check for --sdk_root
            if raw_arg.startswith("--sdk_root="):
                if has_sdk_root:
                    return False, "AMBIGUOUS_REPEATED_FLAG: --sdk_root"
                val = raw_arg.split("=", 1)[1].strip("\"'")
                if not val:
                    return False, "EMPTY_SDK_ROOT_VALUE"
                has_sdk_root = True
                i += 1
                continue
            elif raw_arg == "--sdk_root":
                if has_sdk_root:
                    return False, "AMBIGUOUS_REPEATED_FLAG: --sdk_root"
                if i + 1 >= len(args) or args[i + 1].startswith("-"):
                    return False, "MISSING_SDK_ROOT_VALUE"
                val = args[i + 1].strip("\"'")
                if not val:
                    return False, "EMPTY_SDK_ROOT_VALUE"
                has_sdk_root = True
                i += 2
                continue

            # Check for --list
            if raw_arg == "--list":
                if has_list:
                    return False, "AMBIGUOUS_REPEATED_FLAG: --list"
                has_list = True
                i += 1
                continue

            # Check for --verbose
            if raw_arg == "--verbose":
                if has_verbose:
                    return False, "AMBIGUOUS_REPEATED_FLAG: --verbose"
                has_verbose = True
                i += 1
                continue

            # Check for --channel=0 or --channel 0
            if raw_arg == "--channel=0":
                if has_channel_0:
                    return False, "AMBIGUOUS_REPEATED_FLAG: --channel=0"
                has_channel_0 = True
                i += 1
                continue
            elif raw_arg.startswith("--channel="):
                return False, f"DISALLOWED_CHANNEL_VALUE: {raw_arg}"
            elif raw_arg == "--channel":
                if has_channel_0:
                    return False, "AMBIGUOUS_REPEATED_FLAG: --channel"
                if i + 1 < len(args) and args[i + 1].strip("\"'") == "0":
                    has_channel_0 = True
                    i += 2
                    continue
                else:
                    channel_val = args[i + 1] if i + 1 < len(args) else "MISSING"
                    return False, f"DISALLOWED_CHANNEL_VALUE: --channel {channel_val}"

            # If it starts with '-', it's an unauthorized flag
            if raw_arg.startswith("-"):
                return False, f"DISALLOWED_OR_UNKNOWN_FLAG: {raw_arg}"

            # Otherwise it is a positional argument (e.g. package name)
            return False, f"POSITIONAL_ARGUMENT_PROHIBITED: {raw_arg}"

        if not has_sdk_root:
            return False, "MISSING_MANDATORY_FLAG: --sdk_root"
        if not has_list:
            return False, "MISSING_MANDATORY_FLAG: --list"
        if not has_verbose:
            return False, "MISSING_MANDATORY_FLAG: --verbose"
        if not has_channel_0:
            return False, "MISSING_MANDATORY_FLAG: --channel=0"

        return True, None

    def verify_emulator_invocation(
        self, args: List[str], help_proved_gpu: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Verifies direct emulator CLI argument list under strict allowlist:
        - `["-help"]` is permitted.
        - `["-help-gpu"]` is permitted ONLY IF help_proved_gpu is True.
        All other argument configurations are rejected.
        """
        clean_args = [a.strip("\"'") for a in args]
        if clean_args == ["-help"]:
            return True, None
        elif clean_args == ["-help-gpu"]:
            if help_proved_gpu:
                return True, None
            return False, "GPU_HELP_INTERFACE_NOT_PREVIOUSLY_PROVED"
        return False, f"UNAUTHORIZED_EMULATOR_ARGUMENTS: {args}"

    def verify_script(self, script_text: str) -> Tuple[bool, List[str]]:
        """
        Scans script text against forbidden patterns and verifies structural
        compliance of sdkmanager and emulator invocations.
        Normalizes line continuations and checks line-by-line and across text.
        Returns (is_valid, list_of_violations).
        """
        violations = []

        # Normalize line continuations (backslash followed by newline)
        normalized_text = re.sub(r"\\(?:\r?\n)", " ", script_text)

        all_rules = self.PROHIBITED_TOOL_PATTERNS + self.PROHIBITED_SPECIFIC_PATTERNS

        for pattern, reason in all_rules:
            if re.search(pattern, normalized_text, re.IGNORECASE):
                if reason not in violations:
                    violations.append(reason)

        for line in normalized_text.splitlines():
            clean_line = line.strip()
            if not clean_line or clean_line.startswith("#"):
                continue

            # Check sdkmanager invocations in script
            sdkm_match = re.search(
                rf'(?:^|[;&|`\s\(\)])["\']?(?:[\w./\\:-]*[/\\:])?sdkmanager(?:\.bat)?["\']?(?:\s+(.*?))?(?:$|[;&|`\)])',
                clean_line,
                re.IGNORECASE,
            )
            if sdkm_match:
                args_str = sdkm_match.group(1) or ""
                try:
                    args = shlex.split(args_str)
                except ValueError:
                    args = [a.strip("\"'") for a in args_str.split() if a.strip()]
                is_valid_sdkm, sdkm_err = self.verify_sdkmanager_invocation(args)
                if not is_valid_sdkm:
                    viol = f"SDKMANAGER_INVOCATION_VIOLATION: {sdkm_err}"
                    if viol not in violations:
                        violations.append(viol)

            # Check emulator invocations in script
            emu_match = re.search(
                rf'(?:^|[;&|`\s\(\)])["\']?(?:[\w./\\:-]*[/\\:])?emulator(?:\.exe)?["\']?(?:\s+(.*?))?(?:$|[;&|`\)])',
                clean_line,
                re.IGNORECASE,
            )
            if emu_match:
                args_str = emu_match.group(1) or ""
                try:
                    args = shlex.split(args_str)
                except ValueError:
                    args = [a.strip("\"'") for a in args_str.split() if a.strip()]
                if args not in [["-help"], ["-help-gpu"]]:
                    viol = f"UNAUTHORIZED_EMULATOR_COMMAND: {clean_line}"
                    if viol not in violations:
                        violations.append(viol)

        return (len(violations) == 0, violations)


# -----------------------------------------------------------------------------
# 4. CLI INTERFACE
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ALVORADA Catalog Core Contracts & Static Policy Verifier"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Subcommand: canonicalize
    canon_p = subparsers.add_parser(
        "canonicalize", help="Canonicalize JSON file according to ALVORADA_CANONICAL_JSON_V1"
    )
    canon_p.add_argument("json_path", help="Path to JSON file to canonicalize")

    # Subcommand: parse
    parse_p = subparsers.add_parser(
        "parse", help="Parse raw sdkmanager output into ALVORADA_CATALOG_PROJECTION_V1"
    )
    parse_p.add_argument(
        "--input", "-i", required=True, help="Path to raw sdkmanager output (or '-' for stdin)"
    )
    parse_p.add_argument("--output", "-o", help="Optional path to write projection JSON")
    parse_p.add_argument("--repo-sha", default="", help="Git SHA of repository")
    parse_p.add_argument("--run-id", default="", help="CI Run ID")

    # Subcommand: verify-policy
    verify_p = subparsers.add_parser(
        "verify-policy", help="Verify script against CatalogReadOnlyPolicy"
    )
    verify_p.add_argument("script_path", help="Path to script file (or '-' for stdin)")

    args = parser.parse_args()

    if args.subcommand == "canonicalize":
        with open(args.json_path, "r", encoding="utf-8") as f:
            content = f.read()
        data = json_loads_canonical(content)
        canon_bytes = canonicalize_json_v1(data)
        h = hashlib.sha256(canon_bytes).hexdigest()
        print(f"CANONICAL_SHA256={h}")
        sys.stdout.buffer.write(canon_bytes)
        sys.stdout.buffer.write(b"\n")
        sys.exit(0)

    elif args.subcommand == "parse":
        if args.input == "-":
            raw_text = sys.stdin.read()
        else:
            with open(args.input, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()

        meta = {}
        if args.repo_sha:
            meta["repo_sha"] = args.repo_sha
        if args.run_id:
            meta["run_id"] = args.run_id

        parser_obj = CatalogParser(raw_text, metadata=meta)
        projection = parser_obj.parse()

        canon_bytes = canonicalize_json_v1(projection)
        if args.output:
            with open(args.output, "wb") as f:
                f.write(canon_bytes)
                f.write(b"\n")

        print(f"PROJECTION_SHA256={hashlib.sha256(canon_bytes).hexdigest()}")
        print(f"IS_COMPLETE={'YES' if projection['is_complete'] else 'NO'}")
        print(f"HAS_AMBIGUITY={'YES' if projection['has_ambiguity'] else 'NO'}")
        for pkg in projection["packages"]:
            print(
                f"PACKAGE:{pkg['package_path']}:STATE={pkg['state']}:"
                f"CATALOG={pkg.get('catalog_revision')}:INSTALLED={pkg.get('installed_revision')}"
            )
        sys.exit(0 if projection["is_complete"] and not projection["has_ambiguity"] else 2)

    elif args.subcommand == "verify-policy":
        if args.script_path == "-":
            script_text = sys.stdin.read()
        else:
            with open(args.script_path, "r", encoding="utf-8") as f:
                script_text = f.read()

        verifier = CatalogReadOnlyPolicy()
        is_valid, violations = verifier.verify_script(script_text)
        if is_valid:
            print("CATALOG_READ_ONLY_POLICY=PASS")
            sys.exit(0)
        else:
            print("CATALOG_READ_ONLY_POLICY=FAIL")
            for v in violations:
                print(f"VIOLATION={v}")
            sys.exit(1)


if __name__ == "__main__":
    main()
