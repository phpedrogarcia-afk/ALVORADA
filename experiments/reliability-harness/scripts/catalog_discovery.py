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


class Wave1PreflightVerifier:
    """
    Verifies that Wave 1 package provisioning conforms strictly to the
    frozen catalog proposal and contract requirements of 05R-F.
    """

    EXPECTED_WAVE1_INSTALLS = [
        "emulator",
        "system-images;android-36;default;x86_64",
    ]

    EXPECTED_WAVE1_PREEXISTING = [
        "build-tools;36.0.0",
        "platform-tools",
        "platforms;android-36",
    ]

    def __init__(self, proposal_path: str):
        self.proposal_path = proposal_path

    def verify_and_plan(self, enforce_approval: bool = False) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        Validates the proposal and produces the execution plan for Wave 1.
        Returns (is_valid, plan_details, errors).
        """
        errors = []
        try:
            with open(self.proposal_path, "r", encoding="utf-8") as f:
                proposal = json.load(f)
        except Exception as e:
            return False, {}, [f"FAILED_TO_READ_PROPOSAL: {e}"]

        if proposal.get("contract") != "ALVORADA_CATALOG_LOCK_PROPOSAL_V1":
            errors.append(f"INVALID_CONTRACT: {proposal.get('contract')}")

        # Verify internal cryptographic payload hash against canonical discovery state.
        # Discovery hash was sealed with lock_approved="NO"; this binds the packages,
        # revisions, and metadata immutably to the CI discovery run (35540374123)
        # while permitting human approval to toggle lock_approved to "YES".
        recorded_sha256 = proposal.get("proposal_sha256")
        discovery_payload = {k: v for k, v in proposal.items() if k != "proposal_sha256"}
        discovery_payload["lock_approved"] = "NO"
        computed_sha256 = hash_canonical_json_v1(discovery_payload)

        if recorded_sha256 != computed_sha256:
            errors.append(f"HASH_MISMATCH: recorded={recorded_sha256} computed={computed_sha256}")

        # Check approval status
        lock_approved = proposal.get("lock_approved", "NO") == "YES"
        if enforce_approval and not lock_approved:
            errors.append("LOCK_NOT_APPROVED_BY_FOUNDER")

        packages = proposal.get("packages", {})
        required_installs = []
        preexisting_verified = []

        for pkg in HARD_LOCK_PACKAGES:
            info = packages.get(pkg)
            if not info:
                errors.append(f"PACKAGE_MISSING_FROM_PROPOSAL: {pkg}")
                continue

            state = info.get("state")
            cat_rev = info.get("catalog_revision")

            if pkg in self.EXPECTED_WAVE1_INSTALLS:
                if state != PACKAGE_STATE_ABSENT:
                    errors.append(f"UNEXPECTED_STATE_FOR_WAVE1_INSTALL: {pkg} is {state}, expected {PACKAGE_STATE_ABSENT}")
                required_installs.append({
                    "package": pkg,
                    "target_revision": cat_rev,
                })
            elif pkg in self.EXPECTED_WAVE1_PREEXISTING:
                if state != PACKAGE_STATE_PRESENT_MATCHING:
                    errors.append(f"UNEXPECTED_STATE_FOR_PREEXISTING: {pkg} is {state}, expected {PACKAGE_STATE_PRESENT_MATCHING}")
                preexisting_verified.append({
                    "package": pkg,
                    "installed_revision": info.get("installed_revision"),
                })

        plan = {
            "contract": "ALVORADA_WAVE1_PROVISIONING_PLAN_V1",
            "proposal_sha256": computed_sha256,
            "lock_approved": lock_approved,
            "required_installs": required_installs,
            "preexisting_verified": preexisting_verified,
            "ready_for_execution": len(errors) == 0 and (lock_approved or not enforce_approval),
        }

        return len(errors) == 0, plan, errors


class Wave2AvdConfigurator:
    """
    Defines and verifies the canonical AVD hardware profile, creation syntax,
    and headless launch flags for Wave 2 (05R-G).
    """

    CANONICAL_AVD_NAME = "alvorada_e1_api36_x86_64"
    CANONICAL_PACKAGE = "system-images;android-36;default;x86_64"
    CANONICAL_TAG = "default"
    CANONICAL_ABI = "x86_64"

    # Host budget ceilings for standard GitHub-hosted runner (4 vCPU, 16 GB RAM)
    MAX_ALLOWED_RAM_MB = 3072
    MAX_ALLOWED_CPU_CORES = 2

    CANONICAL_HARDWARE_CONFIG = {
        "AvdId": CANONICAL_AVD_NAME,
        "avd.ini.displayname": "Alvorada E1 API 36 x86_64",
        "abi.type": CANONICAL_ABI,
        "tag.id": CANONICAL_TAG,
        "tag.display": "Default Android System Image",
        "hw.cpu.arch": "x86_64",
        "hw.cpu.ncore": "2",
        "hw.ramSize": "2048",
        "vm.heapSize": "256",
        "hw.lcd.density": "420",
        "hw.lcd.width": "1080",
        "hw.lcd.height": "2400",
        "hw.gpu.enabled": "yes",
        "hw.gpu.mode": "swiftshader_indirect",
        "hw.keyboard": "yes",
        "hw.audioInput": "no",
        "hw.audioOutput": "yes",
        "hw.camera.back": "none",
        "hw.camera.front": "none",
        "disk.dataPartition.size": "2048M",
        "PlayStore.enabled": "false",
        "image.sysdir.1": "system-images/android-36/default/x86_64/",
    }

    CANONICAL_EMULATOR_ARGS = [
        "-avd", CANONICAL_AVD_NAME,
        "-no-window",
        "-no-boot-anim",
        "-no-snapshot",
        "-wipe-data",
        "-gpu", "swiftshader_indirect",
        "-accel", "on",
        "-timezone", "America/Sao_Paulo",
        "-camera-back", "none",
        "-camera-front", "none",
    ]

    @classmethod
    def get_canonical_config(cls) -> Dict[str, str]:
        return dict(cls.CANONICAL_HARDWARE_CONFIG)

    @classmethod
    def get_create_command_args(cls, device_profile: str = "pixel") -> List[str]:
        return [
            "avdmanager", "create", "avd",
            "--name", cls.CANONICAL_AVD_NAME,
            "--package", cls.CANONICAL_PACKAGE,
            "--tag", cls.CANONICAL_TAG,
            "--abi", cls.CANONICAL_ABI,
            "--device", device_profile,
            "--force",
        ]

    @classmethod
    def get_headless_launch_args(cls) -> List[str]:
        return list(cls.CANONICAL_EMULATOR_ARGS)

    @classmethod
    def verify_config(cls, config: Dict[str, str]) -> Tuple[bool, List[str]]:
        errors = []
        ram_str = config.get("hw.ramSize", "0")
        try:
            ram_mb = int(ram_str)
            if ram_mb > cls.MAX_ALLOWED_RAM_MB:
                errors.append(f"RAM_EXCEEDS_HOST_BUDGET: {ram_mb}MB > {cls.MAX_ALLOWED_RAM_MB}MB")
            elif ram_mb < 1024:
                errors.append(f"RAM_INSUFFICIENT_FOR_API36: {ram_mb}MB < 1024MB")
        except ValueError:
            errors.append(f"INVALID_RAM_VALUE: {ram_str}")

        cpu_str = config.get("hw.cpu.ncore", "0")
        try:
            cpu_cores = int(cpu_str)
            if cpu_cores > cls.MAX_ALLOWED_CPU_CORES:
                errors.append(f"CPU_CORES_EXCEED_HOST_BUDGET: {cpu_cores} > {cls.MAX_ALLOWED_CPU_CORES}")
            elif cpu_cores < 1:
                errors.append(f"INVALID_CPU_CORES: {cpu_cores}")
        except ValueError:
            errors.append(f"INVALID_CPU_VALUE: {cpu_str}")

        if config.get("abi.type") != cls.CANONICAL_ABI:
            errors.append(f"WRONG_ABI: {config.get('abi.type')} != {cls.CANONICAL_ABI}")

        if config.get("tag.id") != cls.CANONICAL_TAG:
            errors.append(f"WRONG_TAG: {config.get('tag.id')} != {cls.CANONICAL_TAG}")

        allowed_gpu = {"swiftshader_indirect", "off", "auto-no-window"}
        gpu_mode = config.get("hw.gpu.mode")
        if gpu_mode not in allowed_gpu:
            errors.append(f"DISALLOWED_GPU_MODE: {gpu_mode}")

        return len(errors) == 0, errors

    @classmethod
    def generate_specification_summary(cls) -> Dict[str, Any]:
        return {
            "contract": "ALVORADA_WAVE2_AVD_SPECIFICATION_V1",
            "avd_name": cls.CANONICAL_AVD_NAME,
            "target_package": cls.CANONICAL_PACKAGE,
            "abi": cls.CANONICAL_ABI,
            "tag": cls.CANONICAL_TAG,
            "api_level": 36,
            "resource_budget": {
                "guest_ram_mb": 2048,
                "guest_vcpus": 2,
                "host_ram_headroom_mb": 14336,
                "host_vcpu_headroom": 2,
                "disk_data_partition": "2048M",
            },
            "create_command": " ".join(cls.get_create_command_args()),
            "launch_command": "emulator " + " ".join(cls.get_headless_launch_args()),
            "hardware_config": cls.get_canonical_config(),
        }


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

    # Subcommand: wave1-preflight
    wave1_p = subparsers.add_parser("wave1-preflight", help="Validate catalog lock proposal and generate Wave 1 plan")
    wave1_p.add_argument("--proposal", "-p", required=True, help="Path to canonical_catalog_proposal.json")
    wave1_p.add_argument("--enforce-approval", action="store_true", help="Fail closed if lock_approved is not YES")

    # Subcommand: approve-lock
    approve_p = subparsers.add_parser("approve-lock", help="Founder tool: approve canonical catalog lock proposal")
    approve_p.add_argument("--proposal", "-p", required=True, help="Path to canonical_catalog_proposal.json")

    # Subcommand: wave2-avd-spec
    wave2_p = subparsers.add_parser("wave2-avd-spec", help="Output canonical Wave 2 AVD specification JSON")
    wave2_p.add_argument("--pretty", action="store_true", help="Format JSON with indentation")

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

    elif args.subcommand == "wave1-preflight":
        verifier = Wave1PreflightVerifier(args.proposal)
        is_valid, plan, errors = verifier.verify_and_plan(enforce_approval=args.enforce_approval)
        print(f"WAVE1_VALID={'YES' if is_valid else 'NO'}")
        if is_valid:
            print(f"WAVE1_LOCK_APPROVED={'YES' if plan['lock_approved'] else 'NO'}")
            print(f"WAVE1_PROPOSAL_SHA256={plan['proposal_sha256']}")
            install_pkgs = " ".join(item["package"] for item in plan["required_installs"])
            print(f"WAVE1_INSTALL_PACKAGES={install_pkgs}")
            for item in plan["required_installs"]:
                print(f"WAVE1_TARGET:{item['package']}:REV={item['target_revision']}")
            for item in plan["preexisting_verified"]:
                print(f"WAVE1_PREEXISTING:{item['package']}:INSTALLED={item['installed_revision']}")
            print(f"WAVE1_READY_FOR_EXECUTION={'YES' if plan['ready_for_execution'] else 'NO'}")
            sys.exit(0 if plan['ready_for_execution'] else 2)
        else:
            for err in errors:
                print(f"ERROR={err}")
            sys.exit(2)

    elif args.subcommand == "approve-lock":
        try:
            with open(args.proposal, "r", encoding="utf-8") as f:
                proposal = json.load(f)
        except Exception as e:
            print(f"ERROR=FAILED_TO_READ_PROPOSAL: {e}")
            sys.exit(2)

        verifier = Wave1PreflightVerifier(args.proposal)
        is_valid, plan, errors = verifier.verify_and_plan(enforce_approval=False)
        if not is_valid:
            print("ERROR=CANNOT_APPROVE_INVALID_PROPOSAL")
            for err in errors:
                print(f"ERROR={err}")
            sys.exit(2)

        proposal["lock_approved"] = "YES"
        canon_bytes = canonicalize_json_v1(proposal)
        with open(args.proposal, "wb") as f:
            f.write(canon_bytes)
            f.write(b"\n")

        print("LOCK_APPROVED=YES")
        print(f"PROPOSAL_SHA256={proposal['proposal_sha256']}")
        print("STATUS=READY_FOR_WAVE1_EXECUTION")
        sys.exit(0)

    elif args.subcommand == "wave2-avd-spec":
        spec = Wave2AvdConfigurator.generate_specification_summary()
        if args.pretty:
            print(json.dumps(spec, indent=2))
        else:
            canon_bytes = canonicalize_json_v1(spec)
            sys.stdout.buffer.write(canon_bytes)
            sys.stdout.buffer.write(b"\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
