#!/usr/bin/env python3
"""
ALVORADA — Catalog Discovery Engine & Static Policy Verifier
Implements:
- ALVORADA_CANONICAL_JSON_V1 deterministic serialization and hashing
- Fail-closed CatalogParser for the 5 HARD_LOCK packages from sdkmanager list output
- StaticPolicyVerifier enforcing MISSÃO 05R-E-CATALOG-DESIGN-R1 and R1A constraints
"""

import json
import re
import hashlib
from typing import Any, Dict, List, Optional, Tuple

HARD_LOCK_PACKAGES = [
    "emulator",
    "platform-tools",
    "platforms;android-36",
    "build-tools;36.0.0",
    "system-images;android-36;default;x86_64",
]

# Package states mandated by 05R-E Section 9
PACKAGE_STATE_ABSENT = "ABSENT"
PACKAGE_STATE_PRESENT_MATCHING = "PRESENT_MATCHING_CATALOG"
PACKAGE_STATE_PRESENT_DIFFERENT = "PRESENT_DIFFERENT_REVISION"
PACKAGE_STATE_CATALOG_MISSING = "CATALOG_ENTRY_MISSING"
PACKAGE_STATE_METADATA_AMBIGUOUS = "METADATA_AMBIGUOUS"

def canonicalize_json_v1(data: Any) -> bytes:
    """
    ALVORADA_CANONICAL_JSON_V1 serialization:
    - Recursively sorts dictionary keys lexicographically by Unicode code points.
    - Uses strict compact separators (',', ':') with no extra whitespace.
    - Encodes in UTF-8 without BOM.
    """
    def _sort_obj(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _sort_obj(v) for k, v in sorted(obj.items(), key=lambda item: item[0])}
        elif isinstance(obj, list):
            return [_sort_obj(item) for item in obj]
        return obj

    sorted_data = _sort_obj(data)
    json_str = json.dumps(sorted_data, ensure_ascii=False, separators=(",", ":"))
    return json_str.encode("utf-8")


def hash_canonical_json_v1(data: Any) -> str:
    """Computes SHA-256 over ALVORADA_CANONICAL_JSON_V1 payload."""
    raw_bytes = canonicalize_json_v1(data)
    return hashlib.sha256(raw_bytes).hexdigest()


class CatalogParser:
    """
    Fail-closed parser for `sdkmanager --list --verbose --channel=0` output.
    Extracts installed and available revisions strictly for the 5 HARD_LOCK packages.
    """

    def __init__(self, raw_output: str, metadata: Optional[Dict[str, str]] = None):
        self.raw_output = raw_output
        self.metadata = metadata or {}

    def parse(self) -> Dict[str, Any]:
        """
        Parses raw sdkmanager output and returns a structured lock proposal dictionary.
        Fails closed if any ambiguity or formatting violation is detected.
        """
        installed: Dict[str, List[str]] = {}
        available: Dict[str, List[str]] = {}

        current_section = None
        current_pkg = None

        for line in self.raw_output.splitlines():
            line_str = line.strip()

            if "Installed packages:" in line:
                current_section = "installed"
                current_pkg = None
                continue
            elif "Available Packages:" in line or "Available Updates:" in line:
                current_section = "available"
                current_pkg = None
                continue

            if current_section is None or not line_str or line_str.startswith("---"):
                continue

            # Look for package header line (typically path starting with package identifier)
            if not line.startswith(" ") and not line.startswith("\t"):
                current_pkg = line_str.split()[0]
                continue

            # Look for Version: line under package
            if current_pkg and line_str.startswith("Version:"):
                parts = line_str.split(":", 1)
                if len(parts) == 2:
                    ver = parts[1].strip()
                    if current_section == "installed":
                        installed.setdefault(current_pkg, []).append(ver)
                    elif current_section == "available":
                        available.setdefault(current_pkg, []).append(ver)

        packages_projection = {}
        overall_ready = True

        for pkg in HARD_LOCK_PACKAGES:
            inst_list = installed.get(pkg, [])
            avail_list = available.get(pkg, [])

            # Detect ambiguous duplicates
            if len(inst_list) > 1 or len(avail_list) > 1:
                packages_projection[pkg] = {
                    "package_name": pkg,
                    "state": PACKAGE_STATE_METADATA_AMBIGUOUS,
                    "catalog_revision": None,
                    "installed_revision": None,
                    "error": "DUPLICATE_OR_AMBIGUOUS_REVISIONS_DETECTED",
                }
                overall_ready = False
                continue

            inst_rev = inst_list[0] if inst_list else None
            avail_rev = avail_list[0] if avail_list else None

            if avail_rev is None and inst_rev is None:
                state = PACKAGE_STATE_CATALOG_MISSING
                overall_ready = False
            elif inst_rev is None:
                state = PACKAGE_STATE_ABSENT
            elif avail_rev is not None and inst_rev == avail_rev:
                state = PACKAGE_STATE_PRESENT_MATCHING
            elif avail_rev is not None and inst_rev != avail_rev:
                state = PACKAGE_STATE_PRESENT_DIFFERENT
            else:
                state = PACKAGE_STATE_CATALOG_MISSING
                overall_ready = False

            packages_projection[pkg] = {
                "package_name": pkg,
                "state": state,
                "catalog_revision": avail_rev,
                "installed_revision": inst_rev,
            }

        proposal = {
            "contract": "ALVORADA_CATALOG_LOCK_PROPOSAL_V1",
            "ready_for_human_review": overall_ready,
            "lock_approved": "NO",  # Mandatory: LOCK_APPROVED is always NO during discovery
            "packages": packages_projection,
        }
        if self.metadata:
            proposal["metadata"] = self.metadata

        proposal["proposal_sha256"] = hash_canonical_json_v1(proposal)
        return proposal


class StaticPolicyVerifier:
    """
    Verifies that commands and script snippets strictly adhere to the
    READ-ONLY BY CONSTRUCTION model of 05R-E and R1A.
    """

    PROHIBITED_PATTERNS = [
        (r"--licenses", "PROHIBITED_LICENSE_ACCEPTANCE"),
        (r"--install", "PROHIBITED_INSTALL_FLAG"),
        (r"--update", "PROHIBITED_UPDATE_FLAG"),
        (r"--uninstall", "PROHIBITED_UNINSTALL_FLAG"),
        (r"avdmanager\s+create", "PROHIBITED_AVD_CREATION"),
        (r"adb\s+install", "PROHIBITED_APP_INSTALL"),
        (r"emulator\s+(-avd|@)", "PROHIBITED_AVD_LAUNCH"),
        (r"chmod\s+777", "PROHIBITED_PERMISSIVE_CHMOD"),
        (r"yes\s*\|", "PROHIBITED_UNATTENDED_CONFIRMATION"),
    ]

    ALLOWED_EMULATOR_ARGS = ["-help", "-help-gpu"]

    def verify_script(self, script_text: str) -> Tuple[bool, List[str]]:
        """
        Scans script text against forbidden patterns.
        Returns (is_valid, list_of_violations).
        """
        violations = []
        for pattern, reason in self.PROHIBITED_PATTERNS:
            if re.search(pattern, script_text, re.IGNORECASE):
                violations.append(reason)

        return (len(violations) == 0, violations)

    def verify_emulator_invocation(self, args: List[str], help_proved_gpu: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Verifies emulator CLI invocation under R1A allowlist.
        Only allowed:
        - `["-help"]`
        - `["-help-gpu"]` (ONLY IF help_proved_gpu is True)
        """
        if args == ["-help"]:
            return True, None
        elif args == ["-help-gpu"]:
            if help_proved_gpu:
                return True, None
            return False, "GPU_HELP_INTERFACE_NOT_PREVIOUSLY_PROVED"
        return False, f"UNAUTHORIZED_EMULATOR_ARGUMENTS: {args}"


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="ALVORADA Catalog Discovery Engine & Static Policy Verifier")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Subcommand: parse
    parse_p = subparsers.add_parser("parse", help="Parse sdkmanager output into canonical lock proposal")
    parse_p.add_argument("--input", "-i", required=True, help="Path to raw sdkmanager output (or '-' for stdin)")
    parse_p.add_argument("--output", "-o", help="Path to write canonical JSON proposal")
    parse_p.add_argument("--repo-sha", default="", help="Git SHA of repository")
    parse_p.add_argument("--run-id", default="", help="CI Run ID")

    # Subcommand: verify-script
    verify_p = subparsers.add_parser("verify-script", help="Verify script against static safety policy")
    verify_p.add_argument("script_path", help="Path to script file to verify (or '-' for stdin)")

    # Subcommand: canonicalize
    canon_p = subparsers.add_parser("canonicalize", help="Canonicalize JSON file and output SHA-256")
    canon_p.add_argument("json_path", help="Path to JSON file")

    args = parser.parse_args()

    if args.subcommand == "parse":
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
        proposal = parser_obj.parse()

        canon_bytes = canonicalize_json_v1(proposal)

        if args.output:
            with open(args.output, "wb") as f:
                f.write(canon_bytes)
                f.write(b"\n")

        print(f"PROPOSAL_SHA256={proposal['proposal_sha256']}")
        print(f"READY_FOR_HUMAN_REVIEW={'YES' if proposal['ready_for_human_review'] else 'NO'}")
        print(f"LOCK_APPROVED={proposal['lock_approved']}")
        for pkg_name, pkg_info in sorted(proposal["packages"].items()):
            print(f"PACKAGE:{pkg_name}:STATE={pkg_info['state']}:CATALOG={pkg_info.get('catalog_revision')}:INSTALLED={pkg_info.get('installed_revision')}")

        sys.exit(0 if proposal["ready_for_human_review"] else 2)

    elif args.subcommand == "verify-script":
        if args.script_path == "-":
            script_text = sys.stdin.read()
        else:
            with open(args.script_path, "r", encoding="utf-8", errors="replace") as f:
                script_text = f.read()

        verifier = StaticPolicyVerifier()
        is_valid, violations = verifier.verify_script(script_text)
        if is_valid:
            print("STATIC_POLICY_VERIFICATION=PASS")
            sys.exit(0)
        else:
            print("STATIC_POLICY_VERIFICATION=FAIL")
            for v in violations:
                print(f"VIOLATION={v}")
            sys.exit(1)

    elif args.subcommand == "canonicalize":
        with open(args.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        canon_bytes = canonicalize_json_v1(data)
        h = hashlib.sha256(canon_bytes).hexdigest()
        print(f"CANONICAL_SHA256={h}")
        sys.stdout.buffer.write(canon_bytes)
        sys.stdout.buffer.write(b"\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
