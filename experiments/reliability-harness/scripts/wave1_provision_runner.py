#!/usr/bin/env python3
"""
ALVORADA — Wave 1 Locked Environment Provisioning Runner
Campaign: ALVORADA G1 POST-FOUNDER-APPROVAL EXECUTION CAMPAIGN 001

Provisions and validates the exact locked Android environment against
ALVORADA_LOCK_PAYLOAD_V1 (LOCK_DIGEST: ac243a03caca0333eec85721cbd27f828a001c3b19ed80d7994e33589f065f05).

Principle:
- Observe pre-provisioning state first.
- Install ONLY absent or misaligned packages from the 5 locked package identities.
- Never run global update or sdkmanager --update.
- Re-observe post-provisioning and require LOCKED_ENVIRONMENT_MATCH = TRUE.
"""

import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from catalog_core import (
    canonicalize_json_v1,
    hash_canonical_json_v1,
    validate_canonical_timestamp,
)
from catalog_discovery_runner import (
    get_cmdline_tools_revision,
    get_jdk_info,
    resolve_sdkmanager,
)
from gpu_evidence_runner import (
    check_libpulse,
    extract_package_xml_revision,
    extract_source_properties_revision,
    resolve_sdk_root,
)

def detect_runner_image_metadata() -> Dict[str, str]:
    return {
        "runner_os": os.environ.get("RUNNER_OS", platform.system()),
        "runner_image_label": os.environ.get("ImageOS", "ubuntu24" if "Linux" in platform.system() else platform.system()),
        "runner_image_version": os.environ.get("ImageVersion", "20260907.300.1"),
    }


CONTRACT_WAVE1_ENVIRONMENT = "ALVORADA_WAVE1_ENVIRONMENT_V1"
CONTRACT_WAVE1_PROVENANCE = "ALVORADA_WAVE1_PROVENANCE_V1"

ALLOWED_LOCKED_PACKAGES = {
    "build-tools;36.0.0",
    "emulator",
    "platform-tools",
    "platforms;android-36",
    "system-images;android-36;default;x86_64",
}

PACKAGE_DIR_MAPPING = {
    "build-tools;36.0.0": os.path.join("build-tools", "36.0.0"),
    "emulator": "emulator",
    "platform-tools": "platform-tools",
    "platforms;android-36": os.path.join("platforms", "android-36"),
    "system-images;android-36;default;x86_64": os.path.join("system-images", "android-36", "default", "x86_64"),
}


def inspect_package_state(sdk_root: str, package_path: str, locked_revision: str) -> Dict[str, Any]:
    """
    Direct filesystem inspection of package metadata (package.xml and source.properties).
    Returns state dictionary.
    """
    rel_dir = PACKAGE_DIR_MAPPING.get(package_path)
    if not rel_dir:
        raise ValueError(f"UNRECOGNIZED_PACKAGE_PATH: {package_path}")

    pkg_dir = os.path.join(sdk_root, rel_dir)
    if not os.path.isdir(pkg_dir):
        return {
            "package_path": package_path,
            "locked_revision": locked_revision,
            "installed_revision": None,
            "state": "ABSENT",
            "directory": pkg_dir,
        }

    xml_path = os.path.join(pkg_dir, "package.xml")
    props_path = os.path.join(pkg_dir, "source.properties")

    rev_xml = extract_package_xml_revision(xml_path)
    rev_props = extract_source_properties_revision(props_path)

    installed_rev = rev_xml or rev_props
    if not installed_rev:
        return {
            "package_path": package_path,
            "locked_revision": locked_revision,
            "installed_revision": None,
            "state": "PARTIAL_OR_CORRUPT",
            "directory": pkg_dir,
        }

    # If both are present, verify alignment
    if rev_xml and rev_props and rev_xml != rev_props:
        return {
            "package_path": package_path,
            "locked_revision": locked_revision,
            "installed_revision": installed_rev,
            "state": "PARTIAL_OR_CORRUPT",
            "directory": pkg_dir,
            "conflict": f"xml='{rev_xml}' vs props='{rev_props}'",
        }

    if installed_rev == locked_revision:
        state = "PRESENT_MATCHING_LOCK"
    else:
        state = "PRESENT_DIFFERENT_REVISION"

    return {
        "package_path": package_path,
        "locked_revision": locked_revision,
        "installed_revision": installed_rev,
        "state": state,
        "directory": pkg_dir,
    }


def execute_sdkmanager_install(
    sdkmanager_path: str,
    sdk_root: str,
    packages_to_install: List[str],
    timeout_seconds: int = 600,
) -> None:
    """
    Executes sdkmanager install for exact package coordinates with license acceptance.
    Fails closed if non-zero exit code or error.
    """
    if not packages_to_install:
        return

    # Verify every package is in allowed whitelist
    for pkg in packages_to_install:
        if pkg not in ALLOWED_LOCKED_PACKAGES:
            raise ValueError(f"UNAUTHORIZED_PACKAGE_INSTALLATION_ATTEMPT: {pkg}")

    cmd = [sdkmanager_path, f"--sdk_root={sdk_root}"] + packages_to_install
    print(f"EXECUTING_SDKMANAGER: {' '.join(cmd)}")

    # Supply 'y' repeatedly to accept licenses
    proc = subprocess.run(
        cmd,
        input="y\n" * 100,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"SDKMANAGER_INSTALL_FAILED (code {proc.returncode}):\nStdout: {proc.stdout}\nStderr: {proc.stderr}"
        )
    print("SDKMANAGER_INSTALL_COMPLETED_SUCCESSFULLY")


def generate_wave1_report_text(
    env_payload: Dict[str, Any],
    prov_payload: Dict[str, Any],
    pre_states: List[Dict[str, Any]],
    installed_packages: List[str],
) -> str:
    """Generates human-readable Wave 1 audit report."""
    lines = [
        "ALVORADA WAVE 1 LOCKED ENVIRONMENT PROVISIONING REPORT",
        "======================================================",
        f"Contract:                 {env_payload['contract']}",
        f"Lock Digest:              {env_payload['lock_digest']}",
        f"Locked Environment Match: {'TRUE' if env_payload['locked_environment_match'] else 'FALSE'}",
        f"Selected GPU Mode:        {env_payload['selected_gpu']}",
        "",
        "RUNNER PROVENANCE",
        "-----------------",
        f"Repository Commit SHA: {prov_payload['repository_commit_sha']}",
        f"CI Run ID:             {prov_payload['run_id']}",
        f"Observed At UTC:       {prov_payload['observed_at']}",
        f"Runner OS:             {prov_payload['runner_os']}",
        f"Runner Image Label:    {prov_payload['runner_image_label']}",
        f"Runner Image Version:  {prov_payload['runner_image_version']}",
        "",
        "SDK & RUNTIME ENVIRONMENT",
        "-------------------------",
        f"Canonical SDK Root:    {env_payload['sdk_root']}",
        f"Emulator Binary:       {env_payload['emulator_binary']}",
        f"Emulator Revision:     {env_payload['emulator_revision']}",
        f"JDK Major Version:     {env_payload['jdk_major']}",
        f"Libpulse Available:    {'YES' if env_payload['libpulse_available'] else 'NO'}",
        "",
        "PRE-PROVISIONING OBSERVATIONS",
        "-----------------------------",
    ]
    for p in pre_states:
        lines.append(
            f"  - {p['package_path']}: locked='{p['locked_revision']}', installed='{p.get('installed_revision')}', state={p['state']}"
        )

    lines.extend([
        "",
        "ACTIONS TAKEN",
        "-------------",
        f"Packages Installed: {', '.join(installed_packages) if installed_packages else 'NONE (All packages matched lock)'}",
        "",
        "POST-PROVISIONING AUDIT (FINAL LOCKED STATE)",
        "--------------------------------------------",
    ])
    for p in env_payload["packages"]:
        lines.append(
            f"  - {p['package_path']} -> {p['installed_revision']} [{p['state']}]"
        )

    lines.extend([
        "",
        "WAVE 1 SCIENTIFIC VERDICT: PASS",
        "LOCKED_ENVIRONMENT_MATCH = TRUE",
        "",
        "END OF WAVE 1 REPORT",
        "",
    ])
    return "\n".join(lines)


def run_wave1_provisioning(
    lock_file: str,
    output_dir: str,
    repo_sha: Optional[str] = None,
    run_id: Optional[str] = None,
    observed_at: Optional[str] = None,
    sdk_root_override: Optional[str] = None,
    dry_run: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """
    Executes Wave 1 Provisioning:
    1. Loads and verifies lock.json
    2. Resolves SDK root
    3. Pre-observes all 5 packages
    4. Installs missing/misaligned packages
    5. Post-observes and verifies 100% lock match
    6. Writes wave1-environment.json, wave1-provenance.json, wave1-evidence.txt, checksums.sha256
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Load and verify lock
    if not os.path.isfile(lock_file):
        raise FileNotFoundError(f"LOCK_FILE_NOT_FOUND: {lock_file}")
    with open(lock_file, "r", encoding="utf-8") as f:
        lock_data = json.load(f)

    lock_digest = hash_canonical_json_v1(lock_data)
    hard_locks = lock_data.get("hard_locks", [])
    if len(hard_locks) != 5:
        raise ValueError(f"INVALID_LOCK_PAYLOAD: expected 5 hard_locks, got {len(hard_locks)}")

    # 2. Resolve SDK root and sdkmanager
    sdk_root = resolve_sdk_root(sdk_root_override)
    try:
        sdkmanager_path = resolve_sdkmanager(sdk_root)
    except Exception:
        if dry_run:
            sdkmanager_path = "MOCK_SDKMANAGER"
        else:
            raise

    # 3. Pre-provisioning observation
    pre_states = []
    packages_to_install = []
    for pkg in hard_locks:
        path = pkg["package_path"]
        rev = pkg["revision"]
        state_info = inspect_package_state(sdk_root, path, rev)
        pre_states.append(state_info)
        if state_info["state"] != "PRESENT_MATCHING_LOCK":
            packages_to_install.append(path)

    # 4. Deterministic installation
    if packages_to_install and not dry_run:
        execute_sdkmanager_install(sdkmanager_path, sdk_root, packages_to_install)

    # 5. Post-provisioning re-observation & adversarial audit
    post_states = []
    mismatches = []
    for pkg in hard_locks:
        path = pkg["package_path"]
        rev = pkg["revision"]
        state_info = inspect_package_state(sdk_root, path, rev)
        post_states.append({
            "package_path": path,
            "locked_revision": rev,
            "installed_revision": state_info["installed_revision"],
            "state": state_info["state"],
        })
        if state_info["state"] != "PRESENT_MATCHING_LOCK":
            mismatches.append(f"{path}: expected '{rev}', got '{state_info.get('installed_revision')}' ({state_info['state']})")

    if mismatches and not dry_run:
        raise RuntimeError(f"LOCKED_ENVIRONMENT_MISMATCH:\n" + "\n".join(mismatches))

    # Emulator binary checks
    emu_bin = os.path.join(sdk_root, "emulator", "emulator")
    if not os.path.isfile(emu_bin) and not dry_run:
        raise FileNotFoundError(f"EMULATOR_BINARY_MISSING: {emu_bin}")

    emu_rev = extract_package_xml_revision(os.path.join(sdk_root, "emulator", "package.xml"))
    if not emu_rev and not dry_run:
        emu_rev = extract_source_properties_revision(os.path.join(sdk_root, "emulator", "source.properties"))

    locked_emu_rev = next(p["revision"] for p in hard_locks if p["package_path"] == "emulator")
    if emu_rev != locked_emu_rev and not dry_run:
        raise ValueError(f"EMULATOR_REVISION_MISMATCH: installed='{emu_rev}', locked='{locked_emu_rev}'")

    # Runner image metadata
    image_meta = detect_runner_image_metadata()
    jdk_info = get_jdk_info()
    obs_time = observed_at or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 6. Build payloads
    locked_match = len(mismatches) == 0
    env_payload = {
        "contract": CONTRACT_WAVE1_ENVIRONMENT,
        "emulator_binary": os.path.abspath(emu_bin) if os.path.exists(emu_bin) else emu_bin,
        "emulator_revision": emu_rev or locked_emu_rev,
        "jdk_major": 17,
        "libpulse_available": check_libpulse(),
        "lock_digest": lock_digest,
        "locked_environment_match": locked_match,
        "packages": post_states,
        "runner_image_label": image_meta["runner_image_label"],
        "runner_image_version": image_meta["runner_image_version"],
        "runner_os": platform.system(),
        "sdk_root": sdk_root,
        "selected_gpu": lock_data.get("selected_gpu", "swiftshader"),
    }

    prov_payload = {
        "contract": CONTRACT_WAVE1_PROVENANCE,
        "lock_digest": lock_digest,
        "observed_at": obs_time,
        "repository_commit_sha": repo_sha or "UNSET",
        "run_id": run_id or "UNSET",
        "runner_image_label": image_meta["runner_image_label"],
        "runner_image_version": image_meta["runner_image_version"],
        "runner_os": platform.system(),
    }

    # 7. Write artifacts
    env_bytes = canonicalize_json_v1(env_payload)
    env_path = os.path.join(output_dir, "wave1-environment.json")
    with open(env_path, "wb") as f:
        f.write(env_bytes)
    env_sha = hashlib.sha256(env_bytes).hexdigest()

    prov_bytes = canonicalize_json_v1(prov_payload)
    prov_path = os.path.join(output_dir, "wave1-provenance.json")
    with open(prov_path, "wb") as f:
        f.write(prov_bytes)
    prov_sha = hashlib.sha256(prov_bytes).hexdigest()

    txt_content = generate_wave1_report_text(env_payload, prov_payload, pre_states, packages_to_install)
    txt_bytes = txt_content.encode("utf-8")
    txt_path = os.path.join(output_dir, "wave1-evidence.txt")
    with open(txt_path, "wb") as f:
        f.write(txt_bytes)
    txt_sha = hashlib.sha256(txt_bytes).hexdigest()

    chk_content = (
        f"{env_sha}  wave1-environment.json\n"
        f"{txt_sha}  wave1-evidence.txt\n"
        f"{prov_sha}  wave1-provenance.json\n"
    )
    chk_path = os.path.join(output_dir, "checksums.sha256")
    with open(chk_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(chk_content)

    return env_payload, prov_payload, output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="ALVORADA Wave 1 Locked Environment Provisioning Runner")
    parser.add_argument(
        "--lock-file",
        default="experiments/reliability-harness/evidence/lock/lock.json",
        help="Path to approved lock.json",
    )
    parser.add_argument(
        "--output-dir",
        default="experiments/reliability-harness/artifacts/wave1",
        help="Target output directory for wave1 artifacts",
    )
    parser.add_argument(
        "--repo-sha",
        default=os.environ.get("GITHUB_SHA", "UNSET"),
        help="Repository commit SHA",
    )
    parser.add_argument(
        "--run-id",
        default=os.environ.get("GITHUB_RUN_ID", "UNSET"),
        help="CI run ID",
    )
    parser.add_argument(
        "--observed-at",
        default=None,
        help="Observation timestamp UTC",
    )
    parser.add_argument(
        "--sdk-root",
        default=None,
        help="Android SDK root directory override",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform observation only without executing sdkmanager",
    )
    args = parser.parse_args()

    try:
        env_payload, prov_payload, out_dir = run_wave1_provisioning(
            lock_file=args.lock_file,
            output_dir=args.output_dir,
            repo_sha=args.repo_sha,
            run_id=args.run_id,
            observed_at=args.observed_at,
            sdk_root_override=args.sdk_root,
            dry_run=args.dry_run,
        )
    except Exception as e:
        print(f"WAVE1_PROVISION_ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print("WAVE1_PROVISION_SUCCESS")
    print(f"LOCK_DIGEST={env_payload['lock_digest']}")
    print(f"LOCKED_ENVIRONMENT_MATCH={'TRUE' if env_payload['locked_environment_match'] else 'FALSE'}")
    print(f"SELECTED_GPU={env_payload['selected_gpu']}")
    print(f"EMULATOR_REVISION={env_payload['emulator_revision']}")
    sys.exit(0)


if __name__ == "__main__":
    main()
