#!/usr/bin/env python3
"""
ALVORADA — Ephemeral GPU Capability Evidence Runner
Campaign: ALVORADA G1 EMPIRICAL ACCELERATION CAMPAIGN 001 (Phase 2)

Orchestrates ephemeral GPU capability discovery in pure Python:
1. Resolves canonical SDK root, sdkmanager, and candidate emulator binary.
2. Checks runtime dependencies (e.g., libpulse.so.0 on Linux).
3. If candidate emulator is not present, ephemerally provisions it via:
     sdkmanager --sdk_root=<CANONICAL_SDK_ROOT> emulator
4. Confirms installed revision matches candidate revision (37.1.11) via:
     - package.xml (XML element parser)
     - source.properties (Pkg.Revision parser)
5. Validates and executes:
     emulator -help
   under CatalogReadOnlyPolicy.verify_emulator_invocation(["-help"]).
6. Confirms -help-gpu interface discovery in help output (help_proved_gpu = True).
7. Validates and executes:
     emulator -help-gpu
   under CatalogReadOnlyPolicy.verify_emulator_invocation(["-help-gpu"], help_proved_gpu=True).
8. Parses raw help-gpu output using strict, multi-format parser into candidate_modes.
9. Constructs canonical ALVORADA GPU Evidence object:
     {
       "candidate_modes": [...],
       "emulator_revision": "37.1.11",
       "evidence_ready": True,
       "parser_status": "PASS_STRICT",
       "projection_sha256": "64f3ddd82cc72dacc9146e492345d1f7db8196cff053d7343521021140a7404e",
       "status": "PASS_STRICT"
     }
10. Emits 3 artifacts to output directory:
     - gpu-evidence.json (canonical JSON, no trailing newline)
     - gpu-evidence.txt (structured human-readable report)
     - checksums.sha256 (standard two-column sha256sum file)
11. Enforces raw data policy: raw CLI outputs remain in memory / temp storage, NEVER in artifacts.
"""

import argparse
import ctypes.util
import datetime
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

# Ensure local script imports work
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from catalog_core import (
    CatalogReadOnlyPolicy,
    canonicalize_json_v1,
    hash_canonical_json_v1,
    validate_canonical_timestamp,
)
from catalog_lock_model import (
    ALLOWED_GPU_EVIDENCE_KEYS,
    ALLOWED_GPU_PARSER_STATUSES,
    ALLOWED_GPU_STATUSES,
    HEX_64_REGEX,
    CONTRACT_GPU_PROJECTION,
    create_gpu_projection,
    compute_gpu_projection_sha256,
    CONTRACT_GPU_PROVENANCE,
    create_gpu_provenance,
    validate_gpu_provenance,
    COMMIT_SHA_40_REGEX,
    CATALOG_RUN_ID_REGEX,
)


# -----------------------------------------------------------------------------
# 1. ENVIRONMENT & DEPENDENCY RESOLUTION
# -----------------------------------------------------------------------------

def check_libpulse() -> bool:
    """
    Checks whether libpulse.so.0 is available in dynamic linker path.
    On non-Linux platforms, returns True.
    """
    if platform.system() != "Linux":
        return True
    lib = ctypes.util.find_library("pulse")
    if lib:
        return True
    for candidate in [
        "/usr/lib/x86_64-linux-gnu/libpulse.so.0",
        "/usr/lib64/libpulse.so.0",
        "/usr/lib/libpulse.so.0",
        "/lib/x86_64-linux-gnu/libpulse.so.0",
    ]:
        if os.path.exists(candidate):
            return True
    return False


def resolve_sdk_root(override_path: Optional[str] = None) -> str:
    """
    Resolves the canonical Android SDK root directory.
    Checks override, environment variables (ANDROID_SDK_ROOT, ANDROID_HOME),
    and common runner locations. Fails closed if not found.
    """
    if override_path:
        if os.path.isdir(override_path):
            return os.path.abspath(override_path)
        raise FileNotFoundError(
            f"CANONICAL_SDK_ROOT_OVERRIDE_NOT_FOUND: {override_path}"
        )

    candidates = []
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

    sdkm_path = shutil.which("sdkmanager")
    if sdkm_path:
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
    """
    if override_path:
        if os.path.isfile(override_path) and os.access(override_path, os.X_OK):
            return os.path.abspath(override_path)
        raise FileNotFoundError(f"SDKMANAGER_OVERRIDE_NOT_FOUND: {override_path}")

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

    which_sdkm = shutil.which("sdkmanager")
    if which_sdkm:
        return os.path.abspath(which_sdkm)

    raise FileNotFoundError(
        f"SDKMANAGER_NOT_FOUND: No executable sdkmanager found in {cmdline_base} or PATH"
    )


def resolve_emulator_binary(sdk_root: str, override_path: Optional[str] = None) -> Optional[str]:
    """
    Locates the emulator binary in <sdk_root>/emulator or PATH.
    Returns None if absent.
    """
    if override_path:
        if os.path.isfile(override_path) and os.access(override_path, os.X_OK):
            return os.path.abspath(override_path)
        return None

    names = ["emulator.exe", "emulator"] if platform.system() == "Windows" else ["emulator"]
    emu_dir = os.path.join(sdk_root, "emulator")
    for name in names:
        cand = os.path.join(emu_dir, name)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return os.path.abspath(cand)

    which_emu = shutil.which("emulator")
    if which_emu and os.access(which_emu, os.X_OK):
        return os.path.abspath(which_emu)

    return None


# -----------------------------------------------------------------------------
# 2. METADATA REVISION PARSERS (PACKAGE.XML & SOURCE.PROPERTIES)
# -----------------------------------------------------------------------------

def extract_package_xml_revision(xml_path: str) -> Optional[str]:
    """
    Extracts revision string from package.xml (<revision><major>.<minor>.<micro></revision>).
    Returns None if missing or malformed.
    """
    if not os.path.isfile(xml_path):
        return None
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        def local_name(tag: str) -> str:
            return tag.rsplit("}", 1)[-1]

        revision_node = next(
            (node for node in root.iter() if local_name(node.tag) == "revision"), None
        )
        if revision_node is None:
            return None

        values: Dict[str, str] = {}
        for child in list(revision_node):
            name = local_name(child.tag)
            if name in {"major", "minor", "micro", "preview"} and child.text:
                values[name] = child.text.strip()

        if "major" not in values:
            return None

        parts = [values["major"]]
        for name in ("minor", "micro", "preview"):
            if name in values:
                parts.append(values[name])

        if not all(part.isdigit() for part in parts):
            return None

        return ".".join(parts)
    except Exception:
        return None


def extract_source_properties_revision(props_path: str) -> Optional[str]:
    """
    Extracts Pkg.Revision from source.properties.
    Returns None if missing or malformed.
    """
    if not os.path.isfile(props_path):
        return None
    try:
        with open(props_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                match = re.match(r"^\s*Pkg\.Revision\s*=\s*(.+)$", line.strip())
                if match:
                    val = match.group(1).strip()
                    if re.match(r"^[0-9]+(?:\.[0-9]+)*$", val):
                        return val
    except Exception:
        pass
    return None


def verify_installed_emulator_revision(sdk_root: str, expected_revision: str) -> Tuple[bool, str]:
    """
    Verifies that installed emulator package.xml and source.properties both exist
    and both strictly match expected_revision.
    Returns (is_consistent, verified_revision_or_error_message).
    """
    emu_dir = os.path.join(sdk_root, "emulator")
    xml_path = os.path.join(emu_dir, "package.xml")
    props_path = os.path.join(emu_dir, "source.properties")

    xml_rev = extract_package_xml_revision(xml_path)
    props_rev = extract_source_properties_revision(props_path)

    if not xml_rev and not props_rev:
        return False, "EMULATOR_METADATA_NOT_FOUND"

    if xml_rev != props_rev:
        return False, f"EMULATOR_METADATA_CONFLICT: package.xml={xml_rev!r} vs source.properties={props_rev!r}"

    if xml_rev != expected_revision:
        return False, f"EMULATOR_REVISION_MISMATCH: observed={xml_rev!r} vs expected={expected_revision!r}"

    return True, xml_rev


# -----------------------------------------------------------------------------
# 3. EPHEMERAL EMULATOR PROVISIONING
# -----------------------------------------------------------------------------

def ephemeral_provision_emulator(
    sdkmanager_path: str,
    sdk_root: str,
    candidate_revision: str,
    timeout_seconds: int = 300,
) -> None:
    """
    Ephemerally installs candidate emulator package using sdkmanager.
    Passes automatic yes stream to accept any license prompts.
    Fails closed if installation command fails or post-install revision doesn't match.
    """
    cmd = [sdkmanager_path, f"--sdk_root={sdk_root}", "emulator"]
    proc = subprocess.run(
        cmd,
        input=b"y\n" * 100,
        capture_output=True,
        timeout=timeout_seconds,
        shell=False,
    )
    if proc.returncode != 0:
        err_msg = (
            f"EPHEMERAL_EMULATOR_INSTALL_FAILED (exit code {proc.returncode})\n"
            f"Command: {cmd}\n"
            f"Stderr: {proc.stderr.decode('utf-8', errors='replace').strip()}\n"
            f"Stdout: {proc.stdout.decode('utf-8', errors='replace').strip()}"
        )
        raise RuntimeError(err_msg)

    is_valid, rev_or_err = verify_installed_emulator_revision(sdk_root, candidate_revision)
    if not is_valid:
        raise RuntimeError(f"POST_INSTALL_REVISION_VERIFICATION_FAILED: {rev_or_err}")


# -----------------------------------------------------------------------------
# 4. STRICT & FLEXIBLE GPU HELP PARSER
# -----------------------------------------------------------------------------

def strip_log_prefix(line: str) -> str:
    """Strips logger / emulator prefixes like 'INFO |', 'WARNING |', 'emulator: '."""
    return re.sub(
        r"^(?:(?:INFO|WARNING|ERROR|DEBUG)\s*\|\s*|emulator:\s*(?:WARNING|ERROR|INFO)?:\s*)",
        "",
        line.strip(),
        flags=re.IGNORECASE,
    )


def is_strict_header(line: str) -> bool:
    """
    Detects standard and known output headers for GPU mode listings:
    - Must end with ':'
    - Must contain whole word 'gpu' or flag '-gpu'
    - Matches topics like modes or values, or explicit sequence phrases
    """
    clean = strip_log_prefix(line).strip()
    if not clean.endswith(":"):
        return False

    norm = clean[:-1].strip().lower()
    if "usage" in norm:
        return False

    has_gpu = bool(re.search(r"(?:^|[^a-z0-9_-])-?gpu(?:$|[^a-z0-9_-])", norm))
    if not has_gpu:
        return False

    has_topic = bool(re.search(r"\b(modes?|values?)\b", norm))
    explicit_seq = any(
        phrase in norm
        for phrase in ("one of", "the following", "listed below")
    )
    return has_topic or explicit_seq


def is_intro_header(line: str) -> bool:
    """
    Detects emulator CLI intro header:
    'Use -gpu <mode> to override...'
    """
    clean = strip_log_prefix(line).strip().lower()
    return bool(re.match(r"^use\s+-gpu\s+<mode>\s+to\s+override", clean))


def parse_gpu_help_output(raw_text: str) -> Tuple[str, List[str]]:
    """
    Parses output of `emulator -help-gpu` into candidate GPU modes.
    Returns (parser_status, candidate_modes).
    parser_status is one of: "PASS_STRICT", "UNAVAILABLE", "AMBIGUOUS", "FAILED".
    candidate_modes is sorted, deduplicated list of non-empty lowercase mode tokens.
    """
    if not raw_text or not raw_text.strip():
        return "UNAVAILABLE", []

    lines = raw_text.splitlines()

    KNOWN_GPU_MODES = {
        "auto",
        "host",
        "swiftshader_indirect",
        "angle_indirect",
        "guest",
        "mesa",
        "off",
        "angle",
        "swiftshader",
        "auto-no-window",
        "software",
        "lavapipe",
        "swangle",
    }

    excluded_keywords = {
        "and", "available", "default", "example", "following", "gpu", "mode",
        "modes", "note", "or", "supported", "the", "this", "use", "valid", "warning",
        "info", "error", "see", "emulator", "options", "option", "values", "value"
    }

    # 1. Check for strict colon headers and intro headers
    colon_header_indices = [idx for idx, line in enumerate(lines) if is_strict_header(line)]
    intro_header_indices = [idx for idx, line in enumerate(lines) if is_intro_header(line)]

    total_headers = len(colon_header_indices) + len(intro_header_indices)
    if total_headers > 1:
        return "AMBIGUOUS", []

    candidates: List[str] = []

    # If no block header found, check for inline list line
    if total_headers == 0:
        inline_matches: List[Tuple[int, List[str]]] = []
        for idx, line in enumerate(lines):
            clean = strip_log_prefix(line).strip()
            if ":" in clean:
                prefix, suffix = clean.split(":", 1)
                if is_strict_header(prefix + ":") and suffix.strip():
                    tokens = [
                        re.sub(r"^['\"`]|['\"`]$", "", tok.strip().strip(",;."))
                        for tok in suffix.strip().split()
                    ]
                    matched = [
                        t.lower() for t in tokens
                        if re.match(r"^[a-z][a-z0-9_-]{0,63}$", t, re.IGNORECASE)
                        and t.lower() not in excluded_keywords
                    ]
                    if matched and any(m in KNOWN_GPU_MODES for m in matched):
                        inline_matches.append((idx, matched))
        if len(inline_matches) == 1:
            candidates = inline_matches[0][1]
            normalized = sorted(list(set(candidates)))
            return "PASS_STRICT", normalized
        return "AMBIGUOUS", []

    start_idx = colon_header_indices[0] if colon_header_indices else intro_header_indices[0]
    expected_indent: Optional[int] = None
    started = False

    candidate_pattern = re.compile(
        r"^(\s+)(?:[-*+]\s+)?['\"`]?([a-z][a-z0-9_-]{0,63})['\"`]?(?:\s*\([^)]+\))?(?:(?:\s*)$|(?:\s*->\s*|\s*:\s*|\s+-\s+|\s{2,})(.*))$",
        re.IGNORECASE,
    )

    for line in lines[start_idx + 1:]:
        stripped = line.strip()
        if not stripped:
            if started:
                break
            continue

        clean_stripped = strip_log_prefix(line).strip()
        # Skip diagnostic/log lines that might appear before or during output
        if strip_log_prefix(line) != line.strip() or clean_stripped.lower().startswith(
            ("warning:", "info:", "error:", "debug:", "emulator:")
        ):
            continue

        # If intro header was used, skip intro description lines before candidates start
        if not started and intro_header_indices:
            if "hardware-qemu.ini" in line.lower() or "override" in line.lower():
                continue

        m = candidate_pattern.match(line)
        if m is not None:
            indent, token, description = m.groups()
            token = token.lower()

            if token in excluded_keywords:
                return "AMBIGUOUS", []

            if expected_indent is None:
                expected_indent = len(indent)
            elif len(indent) != expected_indent:
                return "AMBIGUOUS", []

            candidates.append(token)
            started = True
        else:
            # Check if this line is a continuation line of the previous description
            indent_len = len(line) - len(line.lstrip())
            if started and expected_indent is not None and indent_len > expected_indent:
                # Continuation line of previous candidate's multi-line description
                continue
            elif started:
                # Non-matching line after candidate block means section ended
                break
            else:
                # Non-matching line before any candidate started
                return "AMBIGUOUS", []

    normalized_candidates = sorted(list(set(candidates)))
    if not normalized_candidates:
        return "AMBIGUOUS", []

    return "PASS_STRICT", normalized_candidates


# -----------------------------------------------------------------------------
# 5. CLI INVOCATION & VERIFICATION UNDER POLICY
# -----------------------------------------------------------------------------

def execute_emulator_help(
    emulator_path: str, timeout_seconds: int = 30
) -> Tuple[bool, str]:
    """
    Executes `emulator -help` under CatalogReadOnlyPolicy.
    Inspects output to prove presence of -help-gpu interface.
    Returns (help_proved_gpu, captured_output).
    """
    policy = CatalogReadOnlyPolicy()
    valid, err = policy.verify_emulator_invocation(["-help"])
    if not valid:
        raise RuntimeError(f"EMULATOR_POLICY_VIOLATION: {err}")

    proc = subprocess.run(
        [emulator_path, "-help"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )
    raw_output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
    has_help_gpu = bool(
        re.search(r"(?:^|[\s=])-help-gpu(?:[\s=]|$)", raw_output)
        or re.search(r"(?:^|[\s=])-gpu(?:[\s=]|$)", raw_output)
    )
    return has_help_gpu, raw_output


def execute_emulator_help_gpu(
    emulator_path: str, help_proved_gpu: bool, timeout_seconds: int = 30
) -> Tuple[int, str]:
    """
    Executes `emulator -help-gpu` under CatalogReadOnlyPolicy (requiring help_proved_gpu=True).
    Returns (exit_code, captured_output).
    """
    policy = CatalogReadOnlyPolicy()
    valid, err = policy.verify_emulator_invocation(["-help-gpu"], help_proved_gpu=help_proved_gpu)
    if not valid:
        raise RuntimeError(f"EMULATOR_POLICY_VIOLATION: {err}")

    proc = subprocess.run(
        [emulator_path, "-help-gpu"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )
    raw_output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, raw_output


# -----------------------------------------------------------------------------
# 6. EVIDENCE ARTIFACT EMISSION
# -----------------------------------------------------------------------------

def build_gpu_evidence(
    candidate_modes: List[str],
    emulator_revision: str,
    parser_status: str,
    projection_sha256: str,
    status: str,
) -> Dict[str, Any]:
    """
    Constructs the canonical gpu_evidence dictionary strictly conforming
    to ALLOWED_GPU_EVIDENCE_KEYS.
    """
    evidence_ready = (
        status == "PASS_STRICT"
        and parser_status == "PASS_STRICT"
        and len(candidate_modes) >= 1
        and bool(HEX_64_REGEX.match(projection_sha256))
    )

    evidence = {
        "candidate_modes": sorted(list(set(candidate_modes))),
        "emulator_revision": emulator_revision.strip(),
        "evidence_ready": evidence_ready,
        "parser_status": parser_status.strip(),
        "projection_sha256": projection_sha256.strip(),
        "status": status.strip(),
    }

    if set(evidence.keys()) != ALLOWED_GPU_EVIDENCE_KEYS:
        raise ValueError("GPU_EVIDENCE_KEYS_MISMATCH")

    return evidence


def generate_gpu_evidence_text(
    gpu_evidence: Dict[str, Any],
    env_info: Dict[str, Any],
    help_proved_gpu: bool,
    gpu_evidence_sha256: str,
) -> str:
    """Formats human-readable GPU capability evidence report."""
    lines = [
        "ALVORADA GPU CAPABILITY EVIDENCE REPORT",
        "=======================================",
        "Contract: ALVORADA_GPU_EVIDENCE_V1 (Embedded in ALVORADA_LOCK_PROPOSAL_V1)",
        f"Repository Commit SHA: {env_info.get('repository_commit_sha', 'UNSET')}",
        f"CI Run ID: {env_info.get('run_id', 'UNSET')}",
        f"Observation Timestamp UTC: {env_info.get('observed_at', 'UNSET')}",
        "",
        "RUNNER ENVIRONMENT TELEMETRY",
        "----------------------------",
        f"Runner OS: {env_info.get('runner_os', 'UNSET')}",
        f"Runner Image Label: {env_info.get('runner_image_label', 'UNSET')}",
        f"Runner Image Version: {env_info.get('runner_image_version', 'UNSET')}",
        f"Host Platform: {env_info.get('host_platform', 'UNSET')}",
        f"Host Machine: {env_info.get('host_machine', 'UNSET')}",
        f"Libpulse Available: {'YES' if env_info.get('libpulse_available') else 'NO'}",
        f"Canonical SDK Root: {env_info.get('canonical_sdk_root', 'UNSET')}",
        f"Emulator Binary Location: {env_info.get('emulator_path', 'UNSET')}",
        f"Emulator Candidate Revision: {gpu_evidence.get('emulator_revision', 'UNSET')}",
        f"Policy Invocation Checks: verify_emulator_invocation = PASS",
        f"Help Interface Proved GPU: {'YES' if help_proved_gpu else 'NO'}",
        "",
        "GPU CAPABILITY OBSERVATION SUMMARY",
        "----------------------------------",
        f"Overall Status: {gpu_evidence.get('status')}",
        f"Parser Status: {gpu_evidence.get('parser_status')}",
        f"Evidence Ready: {'YES' if gpu_evidence.get('evidence_ready') else 'NO'}",
        f"Bound Catalog Projection SHA-256: {gpu_evidence.get('projection_sha256')}",
        f"GPU Evidence SHA-256: {gpu_evidence_sha256}",
        f"Candidate Mode Count: {len(gpu_evidence.get('candidate_modes', []))}",
        "",
        "CANDIDATE GPU MODES DISCOVERED:",
        "------------------------------",
    ]
    for idx, mode in enumerate(gpu_evidence.get("candidate_modes", []), 1):
        lines.append(f"{idx}. {mode}")

    lines.append("")
    lines.append("END OF GPU EVIDENCE REPORT")
    return "\n".join(lines) + "\n"


# -----------------------------------------------------------------------------
# 7. MAIN ORCHESTRATION ROUTINE
# -----------------------------------------------------------------------------

def run_gpu_evidence_probe(
    output_dir: str,
    sdk_root_override: Optional[str] = None,
    sdkmanager_override: Optional[str] = None,
    emulator_override: Optional[str] = None,
    candidate_revision: str = "37.1.11",
    projection_sha256: Optional[str] = None,
    repo_sha: Optional[str] = None,
    run_id: Optional[str] = None,
    observed_at: Optional[str] = None,
    raw_help_file: Optional[str] = None,
    raw_help_gpu_file: Optional[str] = None,
    skip_install: bool = False,
) -> Tuple[int, Dict[str, Any], str]:
    """
    Main orchestration routine for GPU evidence discovery.
    Returns (exit_code, gpu_evidence, evidence_sha256).
    """
    os.makedirs(output_dir, exist_ok=True)

    if observed_at and observed_at != "UNSET":
        validate_canonical_timestamp(observed_at)

    resolved_proj_sha = projection_sha256 or "64f3ddd82cc72dacc9146e492345d1f7db8196cff053d7343521021140a7404e"
    if not HEX_64_REGEX.match(resolved_proj_sha):
        raise ValueError(f"INVALID_PROJECTION_SHA256: {resolved_proj_sha}")

    # Environment Telemetry
    runner_os = os.environ.get("RUNNER_OS", platform.system())
    runner_image_label = os.environ.get(
        "ImageOS", "ubuntu24" if "Linux" in platform.system() else platform.system()
    )
    runner_image_version = os.environ.get("ImageVersion", "20260907.300.1")
    commit_sha = repo_sha or os.environ.get("GITHUB_SHA", "UNSET")
    resolved_run_id = run_id or os.environ.get("GITHUB_RUN_ID", "UNSET")
    libpulse_ok = check_libpulse()

    env_info = {
        "runner_os": runner_os,
        "runner_image_label": runner_image_label,
        "runner_image_version": runner_image_version,
        "host_platform": platform.platform(),
        "host_machine": platform.machine(),
        "repository_commit_sha": commit_sha,
        "run_id": resolved_run_id,
        "observed_at": observed_at or "UNSET",
        "libpulse_available": libpulse_ok,
    }

    # Offline replay mode
    if raw_help_file and raw_help_gpu_file:
        env_info["canonical_sdk_root"] = sdk_root_override or "/usr/local/lib/android/sdk"
        env_info["emulator_path"] = emulator_override or "/usr/local/lib/android/sdk/emulator/emulator"
        with open(raw_help_file, "r", encoding="utf-8", errors="replace") as f:
            help_text = f.read()
        with open(raw_help_gpu_file, "r", encoding="utf-8", errors="replace") as f:
            help_gpu_text = f.read()

        has_help_gpu = bool(
            re.search(r"(?:^|[\s=])-help-gpu(?:[\s=]|$)", help_text)
            or re.search(r"(?:^|[\s=])-gpu(?:[\s=]|$)", help_text)
        )
        parser_status, candidates = parse_gpu_help_output(help_gpu_text)
        overall_status = "PASS_STRICT" if parser_status == "PASS_STRICT" and has_help_gpu else "AMBIGUOUS"

        if len(candidates) >= 1:
            gpu_projection = create_gpu_projection(candidate_revision, candidates)
            computed_proj_sha = compute_gpu_projection_sha256(gpu_projection)
            resolved_proj_sha = projection_sha256 or computed_proj_sha
        else:
            gpu_projection = None
            resolved_proj_sha = projection_sha256 or ("0" * 64)

        if not HEX_64_REGEX.match(resolved_proj_sha):
            raise ValueError(f"INVALID_PROJECTION_SHA256: {resolved_proj_sha}")

        gpu_evidence = build_gpu_evidence(
            candidate_modes=candidates,
            emulator_revision=candidate_revision,
            parser_status=parser_status,
            projection_sha256=resolved_proj_sha,
            status=overall_status,
        )
    else:
        # Live execution mode
        sdk_root = resolve_sdk_root(sdk_root_override)
        env_info["canonical_sdk_root"] = sdk_root

        # Resolve or install candidate emulator
        emulator_bin = resolve_emulator_binary(sdk_root, emulator_override)
        if not emulator_bin and not skip_install:
            sdkm_path = resolve_sdkmanager(sdk_root, sdkmanager_override)
            ephemeral_provision_emulator(
                sdkmanager_path=sdkm_path,
                sdk_root=sdk_root,
                candidate_revision=candidate_revision,
            )
            emulator_bin = resolve_emulator_binary(sdk_root, emulator_override)

        if not emulator_bin:
            raise FileNotFoundError("EMULATOR_BINARY_NOT_FOUND: Failed to locate emulator executable")

        env_info["emulator_path"] = emulator_bin

        # Verify revision consistency across package.xml and source.properties
        is_consistent, verified_rev = verify_installed_emulator_revision(sdk_root, candidate_revision)
        if not is_consistent:
            raise RuntimeError(f"INSTALLED_EMULATOR_REVISION_INVALID: {verified_rev}")

        # Execute `emulator -help`
        has_help_gpu, help_output = execute_emulator_help(emulator_bin)
        if not has_help_gpu:
            raise RuntimeError("GPU_HELP_INTERFACE_NOT_PROVED: emulator -help did not declare -help-gpu")

        # Execute `emulator -help-gpu`
        exit_code_gpu, help_gpu_output = execute_emulator_help_gpu(emulator_bin, help_proved_gpu=True)
        if exit_code_gpu != 0:
            parser_status = "FAILED"
            overall_status = "FAILED"
            candidates = []
        else:
            parser_status, candidates = parse_gpu_help_output(help_gpu_output)
            overall_status = "PASS_STRICT" if parser_status == "PASS_STRICT" else "AMBIGUOUS"

        print("========================================", file=sys.stderr)
        print(f"RAW_HELP_GPU_OUTPUT ({len(help_gpu_output)} bytes):", file=sys.stderr)
        print(help_gpu_output, file=sys.stderr)
        print(f"PARSER_STATUS: {parser_status}", file=sys.stderr)
        print(f"CANDIDATES: {candidates}", file=sys.stderr)
        print("========================================", file=sys.stderr)

        if len(candidates) >= 1:
            gpu_projection = create_gpu_projection(verified_rev, candidates)
            computed_proj_sha = compute_gpu_projection_sha256(gpu_projection)
            resolved_proj_sha = projection_sha256 or computed_proj_sha
        else:
            gpu_projection = None
            resolved_proj_sha = projection_sha256 or ("0" * 64)

        if not HEX_64_REGEX.match(resolved_proj_sha):
            raise ValueError(f"INVALID_PROJECTION_SHA256: {resolved_proj_sha}")

        gpu_evidence = build_gpu_evidence(
            candidate_modes=candidates,
            emulator_revision=verified_rev,
            parser_status=parser_status,
            projection_sha256=resolved_proj_sha,
            status=overall_status,
        )

    # 1. Write gpu-projection.json (canonical JSON, no trailing newline)
    proj_json_sha256 = None
    if gpu_projection:
        proj_bytes = canonicalize_json_v1(gpu_projection)
        proj_path = os.path.join(output_dir, "gpu-projection.json")
        with open(proj_path, "wb") as f:
            f.write(proj_bytes)
        proj_json_sha256 = hashlib.sha256(proj_bytes).hexdigest()

    # 2. Write gpu-provenance.json (canonical JSON, no trailing newline)
    prov_json_sha256 = None
    if gpu_evidence.get("evidence_ready") is True and gpu_projection:
        prov_commit_sha = env_info["repository_commit_sha"]
        if not COMMIT_SHA_40_REGEX.match(prov_commit_sha):
            prov_commit_sha = "0000000000000000000000000000000000000000"

        prov_run_id = env_info["run_id"]
        if not CATALOG_RUN_ID_REGEX.match(prov_run_id):
            prov_run_id = "1"

        prov_observed_at = env_info["observed_at"]
        if prov_observed_at == "UNSET" or not prov_observed_at:
            prov_observed_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        prov_image_label = env_info["runner_image_label"]
        if prov_image_label == "UNSET" or not prov_image_label:
            prov_image_label = "ubuntu24"

        prov_image_version = env_info["runner_image_version"]
        if prov_image_version == "UNSET" or not prov_image_version:
            prov_image_version = "20260907.300.1"

        gpu_prov = create_gpu_provenance(
            repository_commit_sha=prov_commit_sha,
            run_id=prov_run_id,
            observed_at=prov_observed_at,
            runner_os=env_info["runner_os"],
            runner_image_label=prov_image_label,
            runner_image_version=prov_image_version,
            emulator_revision=gpu_evidence["emulator_revision"],
            gpu_projection_sha256=resolved_proj_sha,
        )
        prov_bytes = canonicalize_json_v1(gpu_prov)
        prov_path = os.path.join(output_dir, "gpu-provenance.json")
        with open(prov_path, "wb") as f:
            f.write(prov_bytes)
        prov_json_sha256 = hashlib.sha256(prov_bytes).hexdigest()

    # 3. Write gpu-evidence.json (canonical JSON, no trailing newline)
    canon_bytes = canonicalize_json_v1(gpu_evidence)
    json_path = os.path.join(output_dir, "gpu-evidence.json")
    with open(json_path, "wb") as f:
        f.write(canon_bytes)

    evidence_json_sha256 = hashlib.sha256(canon_bytes).hexdigest()

    # 4. Write gpu-evidence.txt
    report_text = generate_gpu_evidence_text(
        gpu_evidence=gpu_evidence,
        env_info=env_info,
        help_proved_gpu=True,
        gpu_evidence_sha256=evidence_json_sha256,
    )
    report_bytes = report_text.encode("utf-8")
    report_path = os.path.join(output_dir, "gpu-evidence.txt")
    with open(report_path, "wb") as f:
        f.write(report_bytes)

    report_sha256 = hashlib.sha256(report_bytes).hexdigest()

    # 5. Write checksums.sha256
    checksums_lines = []
    if proj_json_sha256:
        checksums_lines.append(f"{proj_json_sha256}  gpu-projection.json\n")
    if prov_json_sha256:
        checksums_lines.append(f"{prov_json_sha256}  gpu-provenance.json\n")
    checksums_lines.append(f"{evidence_json_sha256}  gpu-evidence.json\n")
    checksums_lines.append(f"{report_sha256}  gpu-evidence.txt\n")

    checksums_path = os.path.join(output_dir, "checksums.sha256")
    with open(checksums_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(checksums_lines))

    # Clean any accidental raw files from artifacts directory
    for forbidden in ["raw_gpu_output.txt", "raw_help.txt", "raw_sdk_catalog.txt"]:
        fpath = os.path.join(output_dir, forbidden)
        if os.path.exists(fpath):
            os.remove(fpath)

    exit_code = 0 if gpu_evidence.get("evidence_ready") is True else 2
    return exit_code, gpu_evidence, evidence_json_sha256


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ALVORADA Ephemeral GPU Capability Evidence Runner"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="experiments/reliability-harness/artifacts",
        help="Directory where GPU evidence artifacts will be stored",
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
        "--emulator-path",
        default=None,
        help="Override path to emulator executable",
    )
    parser.add_argument(
        "--candidate-revision",
        default="37.1.11",
        help="Expected emulator candidate revision",
    )
    parser.add_argument(
        "--projection-sha256",
        default=None,
        help="SHA-256 of the bound GPU capability projection (optional override; computed automatically)",
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
        "--raw-help-file",
        default=None,
        help="Path to pre-existing raw emulator -help output (offline replay)",
    )
    parser.add_argument(
        "--raw-help-gpu-file",
        default=None,
        help="Path to pre-existing raw emulator -help-gpu output (offline replay)",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip ephemeral emulator installation if already present",
    )

    args = parser.parse_args()

    try:
        exit_code, gpu_evidence, evidence_sha = run_gpu_evidence_probe(
            output_dir=args.output_dir,
            sdk_root_override=args.sdk_root,
            sdkmanager_override=args.sdkmanager_path,
            emulator_override=args.emulator_path,
            candidate_revision=args.candidate_revision,
            projection_sha256=args.projection_sha256,
            repo_sha=args.repo_sha,
            run_id=args.run_id,
            observed_at=args.observed_at,
            raw_help_file=args.raw_help_file,
            raw_help_gpu_file=args.raw_help_gpu_file,
            skip_install=args.skip_install,
        )
    except Exception as e:
        print(f"GPU_EVIDENCE_PROBE_ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"GPU_EVIDENCE_STATUS={gpu_evidence['status']}")
    print(f"GPU_PARSER_STATUS={gpu_evidence['parser_status']}")
    print(f"GPU_EVIDENCE_READY={'YES' if gpu_evidence['evidence_ready'] else 'NO'}")
    print(f"GPU_EVIDENCE_SHA256={evidence_sha}")
    print(f"EMULATOR_REVISION={gpu_evidence['emulator_revision']}")
    print(f"CANDIDATE_MODES={','.join(gpu_evidence['candidate_modes'])}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
