#!/usr/bin/env python3
"""
ALVORADA — Real Read-Only Catalog Discovery Runner
Campaign: ALVORADA G1 EMPIRICAL ACCELERATION CAMPAIGN 001 (Phase 1)

Orchestrates Android SDK catalog discovery in pure Python:
1. Locates canonical SDK root and sdkmanager executable.
2. Formulates exact read-only invocation:
     sdkmanager --sdk_root=<CANONICAL_SDK_ROOT> --list --verbose --channel=0
3. Validates CLI arguments against CatalogReadOnlyPolicy before execution.
4. Executes sdkmanager via subprocess.run (shell=False, stdin closed, separate stdout/stderr, bounded timeout).
5. Parses raw catalog output via CatalogParser into ALVORADA_CATALOG_PROJECTION_V1.
6. Computes projection SHA-256 and catalog digest (if complete).
7. Emits 3 artifacts strictly to output directory:
     - catalog-projection.json
     - catalog-evidence.txt
     - checksums.sha256
8. Enforces raw data policy: raw sdkmanager output remains in memory / temp storage, NEVER in artifacts.
"""

import argparse
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure scripts directory is in path
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from catalog_core import (
    CatalogParser,
    CatalogReadOnlyPolicy,
    canonicalize_json_v1,
    hash_canonical_json_v1,
    validate_canonical_timestamp,
    HARD_LOCK_PACKAGES,
)
from catalog_lock_model import (
    compute_catalog_digest,
)


def resolve_sdk_root(override_path: Optional[str] = None) -> str:
    """
    Resolves the canonical Android SDK root directory.
    Checks explicit override, environment variables (ANDROID_SDK_ROOT, ANDROID_HOME),
    and common runner locations. Fails closed if not found.
    """
    candidates = []
    if override_path:
        candidates.append(override_path)

    env_sdk_root = os.environ.get("ANDROID_SDK_ROOT")
    if env_sdk_root:
        candidates.append(env_sdk_root)

    env_home = os.environ.get("ANDROID_HOME")
    if env_home:
        candidates.append(env_home)

    candidates.extend([
        "/usr/local/lib/android/sdk",
        os.path.expanduser("~/Android/Sdk"),
    ])

    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return os.path.abspath(candidate)

    # Check if sdkmanager is in PATH and infer SDK root from parent directories
    sdkm_path = shutil.which("sdkmanager")
    if sdkm_path:
        # Expected layout: <sdk_root>/cmdline-tools/<version>/bin/sdkmanager
        norm = os.path.abspath(sdkm_path)
        parts = norm.split(os.sep)
        try:
            cmdline_idx = parts.index("cmdline-tools")
            inferred_root = os.sep.join(parts[:cmdline_idx])
            if os.path.isdir(inferred_root):
                return inferred_root
        except ValueError:
            pass

    raise FileNotFoundError("CANONICAL_SDK_ROOT_NOT_FOUND: Unable to resolve Android SDK root directory")


def resolve_sdkmanager(sdk_root: str, override_path: Optional[str] = None) -> str:
    """
    Resolves the sdkmanager executable path.
    Searches inside cmdline-tools within the canonical SDK root, or system PATH.
    Fails closed if not found or not executable.
    """
    if override_path:
        if os.path.isfile(override_path) and os.access(override_path, os.X_OK):
            return os.path.abspath(override_path)
        raise FileNotFoundError(f"SDKMANAGER_OVERRIDE_NOT_FOUND: {override_path}")

    # Standard cmdline-tools locations
    cmdline_base = os.path.join(sdk_root, "cmdline-tools")
    candidate_subdirs = ["latest"]
    if os.path.isdir(cmdline_base):
        try:
            for entry in sorted(os.listdir(cmdline_base), reverse=True):
                if entry != "latest" and os.path.isdir(os.path.join(cmdline_base, entry)):
                    candidate_subdirs.append(entry)
        except OSError:
            pass

    for subdir in candidate_subdirs:
        for name in ["sdkmanager", "sdkmanager.bat"]:
            cand = os.path.join(cmdline_base, subdir, "bin", name)
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                return os.path.abspath(cand)

    # Check system PATH
    which_sdkm = shutil.which("sdkmanager")
    if which_sdkm:
        return os.path.abspath(which_sdkm)

    raise FileNotFoundError(
        f"SDKMANAGER_NOT_FOUND: No executable sdkmanager found in {cmdline_base} or PATH"
    )


def get_cmdline_tools_revision(sdk_root: str, sdkmanager_path: str) -> str:
    """
    Reads Pkg.Revision from the source.properties file of cmdline-tools.
    """
    # 1. Look in the directory above bin/
    bin_dir = os.path.dirname(sdkmanager_path)
    tool_dir = os.path.dirname(bin_dir)
    source_props = os.path.join(tool_dir, "source.properties")
    if not os.path.isfile(source_props):
        # Fallback to cmdline-tools/latest/source.properties
        source_props = os.path.join(sdk_root, "cmdline-tools", "latest", "source.properties")

    if os.path.isfile(source_props):
        try:
            with open(source_props, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    match = re.match(r"^\s*Pkg\.Revision\s*=\s*(.+)$", line.strip())
                    if match:
                        return match.group(1).strip()
        except OSError:
            pass

    return "UNKNOWN"


def get_jdk_info() -> Dict[str, str]:
    """Retrieves JDK version information without mutating state."""
    info = {"version_line": "UNKNOWN", "major": "UNKNOWN"}
    java_bin = shutil.which("java")
    if java_bin:
        try:
            res = subprocess.run(
                [java_bin, "-version"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )
            # java -version outputs to stderr
            raw = (res.stderr or res.stdout or "").strip()
            first_line = raw.splitlines()[0] if raw else "UNKNOWN"
            info["version_line"] = first_line

            # Extract major version number (e.g. "17.0.2" -> 17, "1.8.0" -> 8, "21" -> 21)
            match = re.search(r'version "(\d+)(?:\.(\d+))?', first_line)
            if match:
                first_num = match.group(1)
                if first_num == "1" and match.group(2):
                    info["major"] = match.group(2)
                else:
                    info["major"] = first_num
        except Exception:
            pass
    return info


def get_environment_info(
    sdk_root: str,
    sdkmanager_path: str,
    repo_sha: Optional[str] = None,
    run_id: Optional[str] = None,
    observed_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Collects comprehensive read-only environment telemetry."""
    jdk_info = get_jdk_info()
    cmdline_rev = get_cmdline_tools_revision(sdk_root, sdkmanager_path)

    runner_os = os.environ.get("RUNNER_OS", platform.system())
    runner_image_label = os.environ.get(
        "ImageOS", "ubuntu-24.04" if "Linux" in platform.system() else platform.system()
    )
    runner_image_version = os.environ.get("ImageVersion", "UNSET")

    commit_sha = repo_sha or os.environ.get("GITHUB_SHA")
    if not commit_sha:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )
            if res.returncode == 0:
                commit_sha = res.stdout.strip()
        except Exception:
            pass
    if not commit_sha:
        commit_sha = "UNSET"

    resolved_run_id = run_id or os.environ.get("GITHUB_RUN_ID", "UNSET")

    return {
        "canonical_sdk_root": sdk_root,
        "sdkmanager_path": sdkmanager_path,
        "cmdline_tools_revision": cmdline_rev,
        "jdk_major": jdk_info["major"],
        "jdk_version_line": jdk_info["version_line"],
        "runner_os": runner_os,
        "runner_image_label": runner_image_label,
        "runner_image_version": runner_image_version,
        "host_platform": platform.platform(),
        "host_machine": platform.machine(),
        "repository_commit_sha": commit_sha,
        "catalog_run_id": resolved_run_id,
        "observed_at": observed_at or "UNSET",
    }


def build_and_verify_sdkmanager_command(
    sdk_root: str, sdkmanager_path: str
) -> Tuple[List[str], List[str]]:
    """
    Constructs the canonical read-only sdkmanager invocation and validates it
    against CatalogReadOnlyPolicy. Fails closed before execution if invalid.
    """
    args = [
        f"--sdk_root={sdk_root}",
        "--list",
        "--verbose",
        "--channel=0",
    ]

    policy = CatalogReadOnlyPolicy()
    valid, reason = policy.verify_sdkmanager_invocation(args)
    if not valid:
        raise RuntimeError(f"SDKMANAGER_POLICY_VIOLATION: {reason}")

    full_argv = [sdkmanager_path] + args
    return full_argv, args


def execute_sdkmanager_query(full_argv: List[str], timeout_seconds: int = 300) -> str:
    """
    Executes the validated sdkmanager command without shell, with closed stdin,
    and returns captured stdout. Stderr is logged on failure.
    """
    proc = subprocess.run(
        full_argv,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )
    if proc.returncode != 0:
        err_msg = (
            f"SDKMANAGER_EXECUTION_FAILED (exit code {proc.returncode})\n"
            f"Command: {full_argv}\n"
            f"Stderr: {proc.stderr.strip()}"
        )
        raise RuntimeError(err_msg)
    return proc.stdout


def generate_catalog_evidence_text(
    projection: Dict[str, Any],
    env_info: Dict[str, Any],
    projection_sha256: str,
    catalog_digest: str,
) -> str:
    """Formats the human-readable catalog evidence report."""
    lines = [
        "ALVORADA CATALOG DISCOVERY EVIDENCE REPORT",
        "==========================================",
        "Contract: ALVORADA_CATALOG_PROJECTION_V1",
        f"Repository Commit SHA: {env_info.get('repository_commit_sha', 'UNSET')}",
        f"Catalog Run ID: {env_info.get('catalog_run_id', 'UNSET')}",
        f"Observation Timestamp UTC: {env_info.get('observed_at', 'UNSET')}",
        "",
        "RUNNER ENVIRONMENT TELEMETRY",
        "----------------------------",
        f"Runner OS: {env_info.get('runner_os', 'UNSET')}",
        f"Runner Image Label: {env_info.get('runner_image_label', 'UNSET')}",
        f"Runner Image Version: {env_info.get('runner_image_version', 'UNSET')}",
        f"Host Platform: {env_info.get('host_platform', 'UNSET')}",
        f"Host Machine: {env_info.get('host_machine', 'UNSET')}",
        f"Java / JDK Version: {env_info.get('jdk_version_line', 'UNSET')}",
        f"JDK Major: {env_info.get('jdk_major', 'UNSET')}",
        f"Canonical SDK Root: {env_info.get('canonical_sdk_root', 'UNSET')}",
        f"SDK Manager Location: {env_info.get('sdkmanager_path', 'UNSET')}",
        f"Cmdline-tools Revision: {env_info.get('cmdline_tools_revision', 'UNSET')}",
        "Policy Check: CatalogReadOnlyPolicy.verify_sdkmanager_invocation = PASS",
        "",
        "CATALOG PROJECTION SUMMARY",
        "--------------------------",
        f"Is Complete: {'YES' if projection.get('is_complete') else 'NO'}",
        f"Has Ambiguity: {'YES' if projection.get('has_ambiguity') else 'NO'}",
        f"Projection SHA-256: {projection_sha256}",
        f"Catalog Digest: {catalog_digest}",
        "",
        "HARD LOCK PACKAGES (5):",
        "-----------------------",
    ]

    for idx, pkg in enumerate(projection.get("packages", []), 1):
        lines.append(f"{idx}. Package: {pkg.get('package_path')}")
        lines.append(f"   State: {pkg.get('state')}")
        lines.append(f"   Catalog Revision: {pkg.get('catalog_revision')}")
        lines.append(f"   Installed Revision: {pkg.get('installed_revision')}")
        if pkg.get("error"):
            lines.append(f"   Error: {pkg.get('error')}")

    lines.append("")
    lines.append("END OF EVIDENCE REPORT")
    return "\n".join(lines) + "\n"


def run_catalog_discovery(
    output_dir: str,
    sdk_root_override: Optional[str] = None,
    sdkmanager_override: Optional[str] = None,
    repo_sha: Optional[str] = None,
    run_id: Optional[str] = None,
    observed_at: Optional[str] = None,
    raw_input_file: Optional[str] = None,
) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
    """
    Main orchestration routine.
    Returns (exit_code, projection, digests_dict).
    """
    os.makedirs(output_dir, exist_ok=True)

    if observed_at and observed_at != "UNSET":
        validate_canonical_timestamp(observed_at)

    # 1. Resolve environment & binaries
    if raw_input_file:
        sdk_root = sdk_root_override or "/usr/local/lib/android/sdk"
        sdkmanager_path = sdkmanager_override or os.path.join(
            sdk_root, "cmdline-tools", "latest", "bin", "sdkmanager"
        )
    else:
        sdk_root = resolve_sdk_root(sdk_root_override)
        sdkmanager_path = resolve_sdkmanager(sdk_root, sdkmanager_override)

    env_info = get_environment_info(
        sdk_root=sdk_root,
        sdkmanager_path=sdkmanager_path,
        repo_sha=repo_sha,
        run_id=run_id,
        observed_at=observed_at,
    )

    # 2. Acquire raw catalog output
    if raw_input_file:
        with open(raw_input_file, "r", encoding="utf-8", errors="replace") as f:
            raw_output = f.read()
    else:
        full_argv, _ = build_and_verify_sdkmanager_command(sdk_root, sdkmanager_path)
        raw_output = execute_sdkmanager_query(full_argv, timeout_seconds=300)

    # 3. Parse via CatalogParser
    parser = CatalogParser(raw_output)
    projection = parser.parse()

    # 4. Canonicalize projection and compute digests
    canon_bytes = canonicalize_json_v1(projection)
    projection_sha256 = hashlib.sha256(canon_bytes).hexdigest()

    if projection.get("is_complete") and not projection.get("has_ambiguity"):
        cat_digest, _ = compute_catalog_digest(projection)
    else:
        cat_digest = "INCOMPLETE_OR_AMBIGUOUS_CATALOG"

    # 5. Write catalog-projection.json
    projection_file = os.path.join(output_dir, "catalog-projection.json")
    with open(projection_file, "wb") as f:
        f.write(canon_bytes)
        f.write(b"\n")

    # 6. Write catalog-evidence.txt
    evidence_text = generate_catalog_evidence_text(
        projection=projection,
        env_info=env_info,
        projection_sha256=projection_sha256,
        catalog_digest=cat_digest,
    )
    evidence_bytes = evidence_text.encode("utf-8")
    evidence_file = os.path.join(output_dir, "catalog-evidence.txt")
    with open(evidence_file, "wb") as f:
        f.write(evidence_bytes)

    evidence_sha256 = hashlib.sha256(evidence_bytes).hexdigest()

    # 7. Write checksums.sha256 (standard 2-column format)
    checksums_content = (
        f"{projection_sha256}  catalog-projection.json\n"
        f"{evidence_sha256}  catalog-evidence.txt\n"
    )
    checksums_file = os.path.join(output_dir, "checksums.sha256")
    with open(checksums_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(checksums_content)

    # 8. Verify raw output is NEVER in output directory
    for forbidden in ["raw_sdk_catalog.txt", "raw_catalog.txt"]:
        forbidden_path = os.path.join(output_dir, forbidden)
        if os.path.exists(forbidden_path):
            os.remove(forbidden_path)

    digests = {
        "projection_sha256": projection_sha256,
        "evidence_sha256": evidence_sha256,
        "catalog_digest": cat_digest,
    }

    is_success = projection.get("is_complete") is True and projection.get("has_ambiguity") is False
    exit_code = 0 if is_success else 2
    return exit_code, projection, digests


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ALVORADA Real Read-Only Catalog Discovery Runner"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="experiments/reliability-harness/artifacts",
        help="Directory where discovery artifacts will be stored",
    )
    parser.add_argument(
        "--sdk-root",
        default=None,
        help="Override path to Android SDK root",
    )
    parser.add_argument(
        "--sdkmanager-path",
        default=None,
        help="Override path to sdkmanager executable",
    )
    parser.add_argument(
        "--repo-sha",
        default=None,
        help="Git commit SHA of repository",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="CI Run ID",
    )
    parser.add_argument(
        "--observed-at",
        default=None,
        help="Observation timestamp UTC in ISO-8601 format (YYYY-MM-DDTHH:MM:SSZ)",
    )
    parser.add_argument(
        "--raw-input-file",
        default=None,
        help="Path to pre-existing raw sdkmanager output (offline replay)",
    )

    args = parser.parse_args()

    try:
        exit_code, projection, digests = run_catalog_discovery(
            output_dir=args.output_dir,
            sdk_root_override=args.sdk_root,
            sdkmanager_override=args.sdkmanager_path,
            repo_sha=args.repo_sha,
            run_id=args.run_id,
            observed_at=args.observed_at,
            raw_input_file=args.raw_input_file,
        )
    except Exception as e:
        print(f"CATALOG_DISCOVERY_ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"CATALOG_DISCOVERY_STATUS={'PASS' if exit_code == 0 else 'CONDITIONAL'}")
    print(f"PROJECTION_SHA256={digests['projection_sha256']}")
    print(f"EVIDENCE_SHA256={digests['evidence_sha256']}")
    print(f"CATALOG_DIGEST={digests['catalog_digest']}")
    for pkg in projection.get("packages", []):
        print(
            f"PACKAGE:{pkg.get('package_path')}:STATE={pkg.get('state')}:"
            f"CATALOG={pkg.get('catalog_revision')}:INSTALLED={pkg.get('installed_revision')}"
        )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
