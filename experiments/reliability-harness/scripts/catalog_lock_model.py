#!/usr/bin/env python3
"""
ALVORADA — Three-Digest Catalog Lock Model & Immutable Lock Proposal Contract
Contract Version: RECOVERY-G1-002-R2

Implements:
1. CATALOG_DIGEST: Cryptographic identity of pure stable catalog channel state
   for the 5 HARD_LOCK packages (ALVORADA_CATALOG_DIGEST_PAYLOAD_V1).
2. LOCK_PROPOSAL_DIGEST: Cryptographic identity of the immutable discovery proposal
   containing provenance, environment, freshness, GPU evidence, and ready_for_human_review
   without human decision (ALVORADA_LOCK_PROPOSAL_V1).
3. LOCK_DIGEST: Cryptographic identity of the final lock payload produced only after
   a valid external human decision object selects a validated GPU candidate
   (ALVORADA_LOCK_PAYLOAD_V1).
4. Human Decision Contract & Structural Verifier (ALVORADA_HUMAN_LOCK_DECISION_V1).
   NOTE: Human authority is strictly external. The existence of a valid decision JSON
   does not constitute proof of human identity within the library.
5. Invariants and trust-boundary validations:
   - Dual-window freshness & temporal causality (observed_at <= reviewed_at <= evaluation_time_utc <= fresh_until).
   - Strict fail-closed GPU evidence with lowercase 64-hex projection_sha256 and emulator binding.
   - Closed top-level schema for HumanDecision requiring non-empty review_context.
   - Closed semantic builder input schemas (environment, provenance, freshness, gpu_evidence).
   - Provenance structural format validation (40-char lowercase hex commit SHA, positive decimal run ID).
   - Re-validation of catalog digest payload before use in proposals.
   - Environment and provenance runner image label/version coherence.
   - Explicit ready_for_human_review flag in proposal.
"""

import datetime
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure local module imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog_core import (
    CANONICAL_JSON_CONTRACT,
    HARD_LOCK_PACKAGES,
    PACKAGE_STATE_PRESENT_MATCHING,
    PACKAGE_STATE_ABSENT,
    validate_canonical_timestamp,
    canonicalize_json_v1,
    hash_canonical_json_v1,
)

CONTRACT_CATALOG_DIGEST_PAYLOAD = "ALVORADA_CATALOG_DIGEST_PAYLOAD_V1"
CONTRACT_LOCK_PROPOSAL = "ALVORADA_LOCK_PROPOSAL_V1"
CONTRACT_LOCK_PROPOSAL_V2 = "ALVORADA_LOCK_PROPOSAL_V2"
CONTRACT_GPU_PROJECTION = "ALVORADA_GPU_PROJECTION_V1"
CONTRACT_GPU_PROVENANCE = "ALVORADA_GPU_PROVENANCE_V1"
CONTRACT_CATALOG_PROVENANCE = "ALVORADA_CATALOG_PROVENANCE_V1"
CONTRACT_HUMAN_DECISION = "ALVORADA_HUMAN_LOCK_DECISION_V1"
CONTRACT_LOCK_PAYLOAD = "ALVORADA_LOCK_PAYLOAD_V1"

PROPOSAL_STATE_PENDING = "PENDING_HUMAN_REVIEW"
MAX_FRESHNESS_DAYS = 7

ALLOWED_GPU_STATUSES = {"PASS_STRICT", "UNAVAILABLE", "AMBIGUOUS", "FAILED"}
ALLOWED_GPU_PARSER_STATUSES = {"PASS_STRICT", "UNAVAILABLE", "AMBIGUOUS", "FAILED"}

HEX_64_REGEX = re.compile(r"^[0-9a-f]{64}$")
COMMIT_SHA_40_REGEX = re.compile(r"^[0-9a-f]{40}$")
CATALOG_RUN_ID_REGEX = re.compile(r"^[1-9][0-9]*$")

ALLOWED_HUMAN_DECISION_KEYS = {
    "catalog_digest",
    "contract",
    "decision",
    "proposal_digest",
    "review_context",
    "reviewed_at",
    "selected_gpu",
}

ALLOWED_PROPOSAL_KEYS = {
    "catalog_digest",
    "contract",
    "environment",
    "freshness",
    "gpu_evidence",
    "hard_locks",
    "proposal_state",
    "provenance",
    "ready_for_human_review",
}

ALLOWED_ENVIRONMENT_KEYS = {
    "cmdline_tools_revision",
    "emulator_revision",
    "jdk_major",
    "runner_image_label",
    "runner_image_version",
    "runner_os",
}

ALLOWED_PROVENANCE_KEYS = {
    "catalog_run_id",
    "repository_commit_sha",
    "runner_image_label",
    "runner_image_version",
}

ALLOWED_FRESHNESS_KEYS = {
    "fresh_until",
    "max_age_days",
    "observed_at",
}

ALLOWED_GPU_EVIDENCE_KEYS = {
    "candidate_modes",
    "emulator_revision",
    "evidence_ready",
    "parser_status",
    "projection_sha256",
    "status",
}

ALLOWED_GPU_PROJECTION_KEYS = {
    "candidate_modes",
    "contract",
    "emulator_revision",
}

ALLOWED_GPU_PROVENANCE_KEYS = {
    "contract",
    "emulator_revision",
    "gpu_projection_sha256",
    "observed_at",
    "repository_commit_sha",
    "run_id",
    "runner_image_label",
    "runner_image_version",
    "runner_os",
}

ALLOWED_CATALOG_PROVENANCE_KEYS = {
    "catalog_digest",
    "catalog_projection_sha256",
    "cmdline_tools_revision",
    "contract",
    "jdk_major",
    "observed_at",
    "repository_commit_sha",
    "run_id",
    "runner_image_label",
    "runner_image_version",
    "runner_os",
}

ALLOWED_PROPOSAL_V2_KEYS = {
    "catalog_digest",
    "contract",
    "environment",
    "freshness",
    "gpu_evidence",
    "hard_locks",
    "proposal_state",
    "provenance",
    "ready_for_human_review",
}

ALLOWED_PROVENANCE_V2_KEYS = {
    "catalog_commit_sha",
    "catalog_run_id",
    "gpu_commit_sha",
    "gpu_run_id",
    "runner_image_label",
    "runner_image_version",
}


# -----------------------------------------------------------------------------
# 1. CATALOG DIGEST GENERATION & PRE-CONDITIONS
# -----------------------------------------------------------------------------

def validate_catalog_digest_payload(payload: Any) -> None:
    """
    Strictly validates the structure and invariants of ALVORADA_CATALOG_DIGEST_PAYLOAD_V1.
    Fails closed with TypeError or ValueError if any condition is violated.
    """
    if not isinstance(payload, dict):
        raise TypeError("catalog_digest_payload must be a dictionary")

    allowed_keys = {"channel", "contract", "packages"}
    if set(payload.keys()) != allowed_keys:
        extra = set(payload.keys()) - allowed_keys
        missing = allowed_keys - set(payload.keys())
        raise ValueError(
            f"INVALID_CATALOG_PAYLOAD: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )

    if payload.get("contract") != CONTRACT_CATALOG_DIGEST_PAYLOAD:
        raise ValueError(
            f"INVALID_CATALOG_PAYLOAD: Invalid contract {payload.get('contract')!r}"
        )

    channel = payload.get("channel")
    if not isinstance(channel, int) or channel != 0 or isinstance(channel, bool):
        raise ValueError(
            f"INVALID_CATALOG_PAYLOAD: channel must be integer 0, got {channel!r}"
        )

    packages = payload.get("packages")
    if not isinstance(packages, list) or len(packages) != 5:
        raise ValueError(
            f"INVALID_CATALOG_PAYLOAD: packages must be a list of exactly 5 entries, got {len(packages) if isinstance(packages, list) else type(packages)}"
        )

    pkg_map: Dict[str, str] = {}
    seen_paths: List[str] = []
    allowed_pkg_keys = {"catalog_revision", "package_path"}

    for idx, p in enumerate(packages):
        if not isinstance(p, dict):
            raise TypeError(f"INVALID_CATALOG_PAYLOAD: Package entry [{idx}] must be a dict")
        if set(p.keys()) != allowed_pkg_keys:
            extra = set(p.keys()) - allowed_pkg_keys
            missing = allowed_pkg_keys - set(p.keys())
            raise ValueError(
                f"INVALID_CATALOG_PAYLOAD: Package entry [{idx}] has unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
            )

        path = p.get("package_path")
        rev = p.get("catalog_revision")
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"INVALID_CATALOG_PAYLOAD: Invalid package_path at index {idx}")
        if path in pkg_map:
            raise ValueError(f"INVALID_CATALOG_PAYLOAD: Duplicate package_path {path!r}")
        if not isinstance(rev, str) or not rev.strip():
            raise ValueError(f"INVALID_CATALOG_PAYLOAD: Missing or empty catalog_revision for {path!r}")

        pkg_map[path] = rev.strip()
        seen_paths.append(path)

    expected_set = set(HARD_LOCK_PACKAGES)
    actual_set = set(pkg_map.keys())
    if actual_set != expected_set:
        missing = expected_set - actual_set
        extra = actual_set - expected_set
        raise ValueError(
            f"INVALID_CATALOG_PAYLOAD: Package set mismatch. Missing: {sorted(missing)}, Extra: {sorted(extra)}"
        )

    # Must be sorted strictly lexicographically by package_path
    if seen_paths != sorted(expected_set):
        raise ValueError(
            "INVALID_CATALOG_PAYLOAD: Packages must be sorted lexicographically by package_path"
        )


def create_catalog_digest_payload(projection: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constructs the pure, minimal ALVORADA_CATALOG_DIGEST_PAYLOAD_V1.
    Pre-conditions:
    - projection contract must be ALVORADA_CATALOG_PROJECTION_V1
    - projection.is_complete must be True
    - projection.has_ambiguity must be False
    - All five HARD_LOCK packages must exist exactly once with valid catalog_revision
    - No extra packages allowed
    Fails closed with ValueError if any pre-condition fails.
    """
    if not isinstance(projection, dict):
        raise TypeError("Projection must be a dictionary")

    if projection.get("contract") != "ALVORADA_CATALOG_PROJECTION_V1":
        raise ValueError(
            f"NO_CATALOG_DIGEST: Invalid projection contract {projection.get('contract')!r}"
        )

    if projection.get("is_complete") is not True:
        raise ValueError("NO_CATALOG_DIGEST: Projection is incomplete")

    if projection.get("has_ambiguity") is not False:
        raise ValueError("NO_CATALOG_DIGEST: Projection contains ambiguous metadata")

    packages_in = projection.get("packages")
    if not isinstance(packages_in, list):
        raise ValueError("NO_CATALOG_DIGEST: packages field must be a list")

    pkg_map: Dict[str, str] = {}
    for p in packages_in:
        if not isinstance(p, dict):
            raise ValueError("NO_CATALOG_DIGEST: Package entry must be a dictionary")
        path = p.get("package_path")
        rev = p.get("catalog_revision")
        if not path or not isinstance(path, str):
            raise ValueError("NO_CATALOG_DIGEST: Missing package_path in package entry")
        if path in pkg_map:
            raise ValueError(f"NO_CATALOG_DIGEST: Duplicate package {path!r}")
        if not rev or not isinstance(rev, str) or not rev.strip():
            raise ValueError(f"NO_CATALOG_DIGEST: Missing or empty catalog_revision for {path!r}")
        pkg_map[path] = rev.strip()

    # Must contain exactly the 5 HARD_LOCK packages
    expected_set = set(HARD_LOCK_PACKAGES)
    actual_set = set(pkg_map.keys())
    if actual_set != expected_set:
        missing = expected_set - actual_set
        extra = actual_set - expected_set
        raise ValueError(
            f"NO_CATALOG_DIGEST: Package set mismatch. Missing: {sorted(missing)}, Extra: {sorted(extra)}"
        )

    # Order strictly lexicographically by package_path
    sorted_packages = [
        {
            "catalog_revision": pkg_map[path],
            "package_path": path,
        }
        for path in sorted(expected_set)
    ]

    payload = {
        "channel": 0,
        "contract": CONTRACT_CATALOG_DIGEST_PAYLOAD,
        "packages": sorted_packages,
    }
    validate_catalog_digest_payload(payload)
    return payload


def compute_catalog_digest(projection: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Validates projection pre-conditions and returns (CATALOG_DIGEST, catalog_payload).
    """
    payload = create_catalog_digest_payload(projection)
    digest = hash_canonical_json_v1(payload)
    return digest, payload


def _validate_no_local_paths(data: Any, context: str) -> None:
    """Recursively validates that local absolute/workspace paths do not enter digests."""
    forbidden_path_patterns = [
        re.compile(r"^[a-zA-Z]:[/\\]"),  # Windows drive path (C:\...)
        re.compile(r"^/home/"),          # Linux user directory (/home/...)
        re.compile(r"^/Users/"),         # macOS user directory (/Users/...)
        re.compile(r"/android/sdk"),     # SDK directory path
        re.compile(r"/workspace"),       # CI workspace directory
    ]
    if isinstance(data, str):
        for pat in forbidden_path_patterns:
            if pat.search(data):
                raise ValueError(
                    f"LOCAL_PATH_PROHIBITED: Forbidden path pattern {data!r} in {context}"
                )
    elif isinstance(data, dict):
        for k, v in data.items():
            _validate_no_local_paths(k, f"{context}.key({k})")
            _validate_no_local_paths(v, f"{context}.{k}")
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            _validate_no_local_paths(item, f"{context}[{idx}]")


# -----------------------------------------------------------------------------
# 1b. GPU PROJECTION & PROVENANCE MODELS
# -----------------------------------------------------------------------------

def validate_gpu_projection(projection: Any) -> None:
    if not isinstance(projection, dict):
        raise TypeError("gpu_projection must be a dictionary")
    _validate_no_local_paths(projection, "gpu_projection")
    if set(projection.keys()) != ALLOWED_GPU_PROJECTION_KEYS:
        extra = set(projection.keys()) - ALLOWED_GPU_PROJECTION_KEYS
        missing = ALLOWED_GPU_PROJECTION_KEYS - set(projection.keys())
        raise ValueError(
            f"INVALID_GPU_PROJECTION: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )
    if projection.get("contract") != CONTRACT_GPU_PROJECTION:
        raise ValueError(
            f"INVALID_GPU_PROJECTION_CONTRACT: Expected {CONTRACT_GPU_PROJECTION}, got {projection.get('contract')!r}"
        )
    emu_rev = projection.get("emulator_revision")
    if not isinstance(emu_rev, str) or not emu_rev.strip():
        raise ValueError("INVALID_GPU_PROJECTION: emulator_revision must be a non-empty string")
    modes = projection.get("candidate_modes")
    if not isinstance(modes, list) or len(modes) < 1:
        raise ValueError("INVALID_GPU_PROJECTION: candidate_modes must be a non-empty list")
    for m in modes:
        if not isinstance(m, str) or not re.match(r"^[a-z][a-z0-9_-]{0,63}$", m):
            raise ValueError(f"INVALID_GPU_PROJECTION: Invalid mode token: {m!r}")
    if modes != sorted(list(set(modes))):
        raise ValueError("INVALID_GPU_PROJECTION: candidate_modes must be sorted and deduplicated")


def create_gpu_projection(emulator_revision: str, candidate_modes: List[str]) -> Dict[str, Any]:
    if not isinstance(emulator_revision, str) or not emulator_revision.strip():
        raise ValueError("emulator_revision must be a non-empty string")
    if not isinstance(candidate_modes, (list, set)):
        raise TypeError("candidate_modes must be a list or set")
    dedup_sorted = sorted(list(set(candidate_modes)))
    proj = {
        "candidate_modes": dedup_sorted,
        "contract": CONTRACT_GPU_PROJECTION,
        "emulator_revision": emulator_revision.strip(),
    }
    validate_gpu_projection(proj)
    return proj


def compute_gpu_projection_sha256(projection: Dict[str, Any]) -> str:
    validate_gpu_projection(projection)
    return hash_canonical_json_v1(projection)


def validate_gpu_provenance(prov: Any) -> None:
    if not isinstance(prov, dict):
        raise TypeError("gpu_provenance must be a dictionary")
    _validate_no_local_paths(prov, "gpu_provenance")
    if set(prov.keys()) != ALLOWED_GPU_PROVENANCE_KEYS:
        extra = set(prov.keys()) - ALLOWED_GPU_PROVENANCE_KEYS
        missing = ALLOWED_GPU_PROVENANCE_KEYS - set(prov.keys())
        raise ValueError(
            f"INVALID_GPU_PROVENANCE: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )
    if prov.get("contract") != CONTRACT_GPU_PROVENANCE:
        raise ValueError(
            f"INVALID_GPU_PROVENANCE_CONTRACT: Expected {CONTRACT_GPU_PROVENANCE}, got {prov.get('contract')!r}"
        )
    if not COMMIT_SHA_40_REGEX.match(prov.get("repository_commit_sha", "")):
        raise ValueError("INVALID_GPU_PROVENANCE: repository_commit_sha must be 40 lowercase hex characters")
    if not CATALOG_RUN_ID_REGEX.match(prov.get("run_id", "")):
        raise ValueError("INVALID_GPU_PROVENANCE: run_id must be a positive decimal integer string")
    validate_canonical_timestamp(prov.get("observed_at", ""))
    for s_field in ["runner_os", "runner_image_label", "runner_image_version", "emulator_revision"]:
        val = prov.get(s_field)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"INVALID_GPU_PROVENANCE: {s_field} must be a non-empty string")
    if not HEX_64_REGEX.match(prov.get("gpu_projection_sha256", "")):
        raise ValueError("INVALID_GPU_PROVENANCE: gpu_projection_sha256 must be 64 lowercase hex characters")


def create_gpu_provenance(
    repository_commit_sha: str,
    run_id: str,
    observed_at: str,
    runner_os: str,
    runner_image_label: str,
    runner_image_version: str,
    emulator_revision: str,
    gpu_projection_sha256: str,
) -> Dict[str, Any]:
    prov = {
        "contract": CONTRACT_GPU_PROVENANCE,
        "emulator_revision": emulator_revision.strip(),
        "gpu_projection_sha256": gpu_projection_sha256.strip(),
        "observed_at": observed_at.strip(),
        "repository_commit_sha": repository_commit_sha.strip(),
        "run_id": run_id.strip(),
        "runner_image_label": runner_image_label.strip(),
        "runner_image_version": runner_image_version.strip(),
        "runner_os": runner_os.strip(),
    }
    validate_gpu_provenance(prov)
    return prov


def validate_catalog_provenance(prov: Any) -> None:
    if not isinstance(prov, dict):
        raise TypeError("catalog_provenance must be a dictionary")
    _validate_no_local_paths(prov, "catalog_provenance")
    if set(prov.keys()) != ALLOWED_CATALOG_PROVENANCE_KEYS:
        extra = set(prov.keys()) - ALLOWED_CATALOG_PROVENANCE_KEYS
        missing = ALLOWED_CATALOG_PROVENANCE_KEYS - set(prov.keys())
        raise ValueError(
            f"INVALID_CATALOG_PROVENANCE: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )
    if prov.get("contract") != CONTRACT_CATALOG_PROVENANCE:
        raise ValueError(
            f"INVALID_CATALOG_PROVENANCE_CONTRACT: Expected {CONTRACT_CATALOG_PROVENANCE}, got {prov.get('contract')!r}"
        )
    if not COMMIT_SHA_40_REGEX.match(prov.get("repository_commit_sha", "")):
        raise ValueError("INVALID_CATALOG_PROVENANCE: repository_commit_sha must be 40 lowercase hex characters")
    if not CATALOG_RUN_ID_REGEX.match(prov.get("run_id", "")):
        raise ValueError("INVALID_CATALOG_PROVENANCE: run_id must be a positive decimal integer string")
    validate_canonical_timestamp(prov.get("observed_at", ""))
    jdk_major = prov.get("jdk_major")
    if not isinstance(jdk_major, int) or jdk_major != 17 or isinstance(jdk_major, bool):
        raise ValueError(f"INVALID_CATALOG_PROVENANCE: jdk_major must be integer 17, got {jdk_major!r}")
    for s_field in ["runner_os", "runner_image_label", "runner_image_version", "cmdline_tools_revision"]:
        val = prov.get(s_field)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"INVALID_CATALOG_PROVENANCE: {s_field} must be a non-empty string")
    if not HEX_64_REGEX.match(prov.get("catalog_projection_sha256", "")):
        raise ValueError("INVALID_CATALOG_PROVENANCE: catalog_projection_sha256 must be 64 lowercase hex characters")
    if not HEX_64_REGEX.match(prov.get("catalog_digest", "")):
        raise ValueError("INVALID_CATALOG_PROVENANCE: catalog_digest must be 64 lowercase hex characters")


def create_catalog_provenance(
    repository_commit_sha: str,
    run_id: str,
    observed_at: str,
    runner_os: str,
    runner_image_label: str,
    runner_image_version: str,
    jdk_major: int,
    cmdline_tools_revision: str,
    catalog_projection_sha256: str,
    catalog_digest: str,
) -> Dict[str, Any]:
    prov = {
        "catalog_digest": catalog_digest.strip(),
        "catalog_projection_sha256": catalog_projection_sha256.strip(),
        "cmdline_tools_revision": cmdline_tools_revision.strip(),
        "contract": CONTRACT_CATALOG_PROVENANCE,
        "jdk_major": jdk_major,
        "observed_at": observed_at.strip(),
        "repository_commit_sha": repository_commit_sha.strip(),
        "run_id": run_id.strip(),
        "runner_image_label": runner_image_label.strip(),
        "runner_image_version": runner_image_version.strip(),
        "runner_os": runner_os.strip(),
    }
    validate_catalog_provenance(prov)
    return prov


# -----------------------------------------------------------------------------
# 2. IMMUTABLE LOCK PROPOSAL & STRUCTURAL VALIDATION
# -----------------------------------------------------------------------------


def validate_lock_proposal(proposal: Any) -> None:
    """
    Validates the structure and invariants of ALVORADA_LOCK_PROPOSAL (V1 or V2) before digest
    computation, decision verification, or lock candidate computation.
    Fails closed if any invariant is violated.
    """
    if not isinstance(proposal, dict):
        raise TypeError("proposal must be a dictionary")

    contract = proposal.get("contract")
    if contract == CONTRACT_LOCK_PROPOSAL_V2:
        validate_lock_proposal_v2(proposal)
        return
    elif contract != CONTRACT_LOCK_PROPOSAL:
        raise ValueError(
            f"INVALID_LOCK_PROPOSAL: Invalid contract {contract!r}"
        )

    if set(proposal.keys()) != ALLOWED_PROPOSAL_KEYS:
        extra = set(proposal.keys()) - ALLOWED_PROPOSAL_KEYS
        missing = ALLOWED_PROPOSAL_KEYS - set(proposal.keys())
        raise ValueError(
            f"INVALID_LOCK_PROPOSAL: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )

    if proposal.get("proposal_state") != PROPOSAL_STATE_PENDING:
        raise ValueError(
            f"INVALID_LOCK_PROPOSAL: proposal_state must be {PROPOSAL_STATE_PENDING!r}, got {proposal.get('proposal_state')!r}"
        )

    ready_for_review = proposal.get("ready_for_human_review")
    if not isinstance(ready_for_review, bool):
        raise TypeError(
            f"INVALID_LOCK_PROPOSAL: ready_for_human_review must be boolean, got {type(ready_for_review)}"
        )

    catalog_digest = proposal.get("catalog_digest")
    if not isinstance(catalog_digest, str) or not HEX_64_REGEX.match(catalog_digest):
        raise ValueError("INVALID_LOCK_PROPOSAL: catalog_digest must be lowercase 64-char hex SHA-256")

    # Hard locks validation
    hard_locks = proposal.get("hard_locks")
    if not isinstance(hard_locks, list) or len(hard_locks) != 5:
        raise ValueError("INVALID_LOCK_PROPOSAL: hard_locks must be a list of exactly 5 entries")

    hl_map: Dict[str, str] = {}
    hl_paths: List[str] = []
    allowed_hl_keys = {"package_path", "revision"}
    for idx, hl in enumerate(hard_locks):
        if not isinstance(hl, dict):
            raise TypeError(f"INVALID_LOCK_PROPOSAL: hard_locks[{idx}] must be a dict")
        if set(hl.keys()) != allowed_hl_keys:
            raise ValueError(f"INVALID_LOCK_PROPOSAL: hard_locks[{idx}] has invalid keys")
        path = hl.get("package_path")
        rev = hl.get("revision")
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"INVALID_LOCK_PROPOSAL: Invalid package_path in hard_locks[{idx}]")
        if not isinstance(rev, str) or not rev.strip():
            raise ValueError(f"INVALID_LOCK_PROPOSAL: Invalid revision in hard_locks[{idx}]")
        if path in hl_map:
            raise ValueError(f"INVALID_LOCK_PROPOSAL: Duplicate package_path {path!r} in hard_locks")
        hl_map[path] = rev.strip()
        hl_paths.append(path)

    expected_set = set(HARD_LOCK_PACKAGES)
    if set(hl_map.keys()) != expected_set:
        raise ValueError("INVALID_LOCK_PROPOSAL: hard_locks packages do not match HARD_LOCK_PACKAGES")
    if hl_paths != sorted(expected_set):
        raise ValueError("INVALID_LOCK_PROPOSAL: hard_locks must be sorted lexicographically by package_path")

    # Reconstruct catalog payload from hard_locks and verify against catalog_digest
    reconstructed_cat_payload = {
        "channel": 0,
        "contract": CONTRACT_CATALOG_DIGEST_PAYLOAD,
        "packages": [
            {"catalog_revision": hl_map[p], "package_path": p}
            for p in sorted(expected_set)
        ],
    }
    reconstructed_cat_digest = hash_canonical_json_v1(reconstructed_cat_payload)
    if reconstructed_cat_digest != catalog_digest:
        raise ValueError(
            f"INVALID_LOCK_PROPOSAL: catalog_digest {catalog_digest!r} does not match hard_locks content {reconstructed_cat_digest!r}"
        )

    # Environment validation
    environment = proposal.get("environment")
    if not isinstance(environment, dict):
        raise TypeError("INVALID_LOCK_PROPOSAL: environment must be a dictionary")
    _validate_no_local_paths(environment, "environment")

    if set(environment.keys()) != ALLOWED_ENVIRONMENT_KEYS:
        raise ValueError("INVALID_LOCK_PROPOSAL: environment keys mismatch")

    jdk_major = environment.get("jdk_major")
    if not isinstance(jdk_major, int) or jdk_major != 17 or isinstance(jdk_major, bool):
        raise ValueError(f"INVALID_LOCK_PROPOSAL: environment.jdk_major must be integer 17, got {jdk_major!r}")

    for k in ["cmdline_tools_revision", "emulator_revision", "runner_image_label", "runner_image_version", "runner_os"]:
        v = environment.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"INVALID_LOCK_PROPOSAL: environment.{k} must be a non-empty string")

    # Provenance validation
    provenance = proposal.get("provenance")
    if not isinstance(provenance, dict):
        raise TypeError("INVALID_LOCK_PROPOSAL: provenance must be a dictionary")
    _validate_no_local_paths(provenance, "provenance")

    if set(provenance.keys()) != ALLOWED_PROVENANCE_KEYS:
        raise ValueError("INVALID_LOCK_PROPOSAL: provenance keys mismatch")

    for k in ALLOWED_PROVENANCE_KEYS:
        v = provenance.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"INVALID_LOCK_PROPOSAL: provenance.{k} must be a non-empty string")

    if not COMMIT_SHA_40_REGEX.match(provenance["repository_commit_sha"]):
        raise ValueError(
            "INVALID_LOCK_PROPOSAL: provenance.repository_commit_sha must be exactly 40 lowercase hex characters"
        )
    if not CATALOG_RUN_ID_REGEX.match(provenance["catalog_run_id"]):
        raise ValueError(
            "INVALID_LOCK_PROPOSAL: provenance.catalog_run_id must be a positive decimal integer string"
        )

    # Environment / Provenance coherence
    if environment["runner_image_label"].strip() != provenance["runner_image_label"].strip():
        raise ValueError("INVALID_LOCK_PROPOSAL: runner_image_label mismatch between environment and provenance")
    if environment["runner_image_version"].strip() != provenance["runner_image_version"].strip():
        raise ValueError("INVALID_LOCK_PROPOSAL: runner_image_version mismatch between environment and provenance")

    # Freshness validation
    freshness = proposal.get("freshness")
    if not isinstance(freshness, dict):
        raise TypeError("INVALID_LOCK_PROPOSAL: freshness must be a dictionary")

    if set(freshness.keys()) != ALLOWED_FRESHNESS_KEYS:
        raise ValueError("INVALID_LOCK_PROPOSAL: freshness keys mismatch")

    observed_at = freshness.get("observed_at")
    fresh_until = freshness.get("fresh_until")
    max_age_days = freshness.get("max_age_days")

    if not isinstance(observed_at, str) or not isinstance(fresh_until, str):
        raise ValueError("INVALID_LOCK_PROPOSAL: observed_at and fresh_until must be strings")
    if not isinstance(max_age_days, int) or max_age_days != MAX_FRESHNESS_DAYS or isinstance(max_age_days, bool):
        raise ValueError(f"INVALID_LOCK_PROPOSAL: max_age_days must be integer {MAX_FRESHNESS_DAYS}")

    validate_canonical_timestamp(observed_at)
    validate_canonical_timestamp(fresh_until)

    dt_obs = datetime.datetime.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ")
    dt_fresh = datetime.datetime.strptime(fresh_until, "%Y-%m-%dT%H:%M:%SZ")
    if dt_fresh <= dt_obs:
        raise ValueError("INVALID_LOCK_PROPOSAL: fresh_until must be strictly greater than observed_at")
    delta = dt_fresh - dt_obs
    if delta.days != MAX_FRESHNESS_DAYS or delta.seconds != 0:
        raise ValueError(f"INVALID_LOCK_PROPOSAL: fresh_until must be exactly {MAX_FRESHNESS_DAYS} days after observed_at")

    # GPU Evidence validation
    gpu_evidence = proposal.get("gpu_evidence")
    if not isinstance(gpu_evidence, dict):
        raise TypeError("INVALID_LOCK_PROPOSAL: gpu_evidence must be a dictionary")
    _validate_no_local_paths(gpu_evidence, "gpu_evidence")

    for prohibited in ["selected_gpu", "gpu_mode", "default_gpu"]:
        if prohibited in gpu_evidence:
            raise ValueError(f"GPU_SELECTION_PROHIBITED_IN_PROPOSAL: {prohibited!r} found in gpu_evidence")

    if set(gpu_evidence.keys()) != ALLOWED_GPU_EVIDENCE_KEYS:
        raise ValueError("INVALID_LOCK_PROPOSAL: gpu_evidence keys mismatch")

    gpu_status = gpu_evidence.get("status")
    if gpu_status not in ALLOWED_GPU_STATUSES:
        raise ValueError(f"INVALID_LOCK_PROPOSAL: gpu_evidence.status invalid: {gpu_status!r}")

    parser_status = gpu_evidence.get("parser_status")
    if parser_status not in ALLOWED_GPU_PARSER_STATUSES:
        raise ValueError(f"INVALID_LOCK_PROPOSAL: gpu_evidence.parser_status invalid: {parser_status!r}")

    evidence_ready = gpu_evidence.get("evidence_ready")
    if not isinstance(evidence_ready, bool):
        raise TypeError("INVALID_LOCK_PROPOSAL: gpu_evidence.evidence_ready must be a boolean")

    candidates_raw = gpu_evidence.get("candidate_modes")
    if not isinstance(candidates_raw, list):
        raise TypeError("INVALID_LOCK_PROPOSAL: gpu_evidence.candidate_modes must be a list")
    for m in candidates_raw:
        if not isinstance(m, str) or not m.strip():
            raise ValueError("INVALID_LOCK_PROPOSAL: candidate_modes items must be non-empty strings")
    if candidates_raw != sorted(list(set(candidates_raw))):
        raise ValueError("INVALID_LOCK_PROPOSAL: candidate_modes must be sorted and deduplicated")

    gpu_emu_rev = gpu_evidence.get("emulator_revision")
    if not isinstance(gpu_emu_rev, str) or not gpu_emu_rev.strip():
        raise ValueError("INVALID_LOCK_PROPOSAL: gpu_evidence.emulator_revision must be non-empty string")

    projection_sha256 = gpu_evidence.get("projection_sha256")
    if not isinstance(projection_sha256, str):
        raise ValueError("INVALID_LOCK_PROPOSAL: gpu_evidence.projection_sha256 must be a string")

    # Tripartite emulator revision binding
    env_emu_rev = environment["emulator_revision"].strip()
    hl_emu_rev = hl_map["emulator"]
    if gpu_emu_rev.strip() != env_emu_rev:
        raise ValueError(
            f"INVALID_LOCK_PROPOSAL: gpu_evidence.emulator_revision ({gpu_emu_rev!r}) != environment.emulator_revision ({env_emu_rev!r})"
        )
    if env_emu_rev != hl_emu_rev:
        raise ValueError(
            f"INVALID_LOCK_PROPOSAL: environment.emulator_revision ({env_emu_rev!r}) != hard_locks['emulator'] ({hl_emu_rev!r})"
        )

    if evidence_ready is True:
        if gpu_status != "PASS_STRICT":
            raise ValueError(f"INVALID_LOCK_PROPOSAL: evidence_ready=True requires status='PASS_STRICT', got {gpu_status!r}")
        if parser_status != "PASS_STRICT":
            raise ValueError(f"INVALID_LOCK_PROPOSAL: evidence_ready=True requires parser_status='PASS_STRICT', got {parser_status!r}")
        if len(candidates_raw) < 1:
            raise ValueError("INVALID_LOCK_PROPOSAL: evidence_ready=True requires candidate_modes >= 1")
        if not HEX_64_REGEX.match(projection_sha256):
            raise ValueError(
                f"INVALID_LOCK_PROPOSAL: evidence_ready=True requires valid projection_sha256 (64 hex chars), got {projection_sha256!r}"
            )
        if ready_for_review is not True:
            raise ValueError("INVALID_LOCK_PROPOSAL: ready_for_human_review must be True when evidence_ready=True and all invariants pass")
    else:
        if ready_for_review is not False:
            raise ValueError("INVALID_LOCK_PROPOSAL: ready_for_human_review must be False when evidence_ready=False")


def validate_lock_proposal_v2(proposal: Any) -> None:
    """
    Validates the structure and invariants of ALVORADA_LOCK_PROPOSAL_V2 before digest
    computation, decision verification, or lock candidate computation.
    Fails closed if any invariant is violated.
    """
    if not isinstance(proposal, dict):
        raise TypeError("proposal must be a dictionary")

    _validate_no_local_paths(proposal, "lock_proposal")

    if set(proposal.keys()) != ALLOWED_PROPOSAL_V2_KEYS:
        extra = set(proposal.keys()) - ALLOWED_PROPOSAL_V2_KEYS
        missing = ALLOWED_PROPOSAL_V2_KEYS - set(proposal.keys())
        raise ValueError(
            f"INVALID_LOCK_PROPOSAL_V2: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )

    if proposal.get("contract") != CONTRACT_LOCK_PROPOSAL_V2:
        raise ValueError(
            f"INVALID_LOCK_PROPOSAL_V2: Invalid contract {proposal.get('contract')!r}"
        )

    if proposal.get("proposal_state") != PROPOSAL_STATE_PENDING:
        raise ValueError(
            f"INVALID_LOCK_PROPOSAL_V2: proposal_state must be {PROPOSAL_STATE_PENDING!r}, got {proposal.get('proposal_state')!r}"
        )

    ready_for_review = proposal.get("ready_for_human_review")
    if not isinstance(ready_for_review, bool):
        raise TypeError(
            f"INVALID_LOCK_PROPOSAL_V2: ready_for_human_review must be boolean, got {type(ready_for_review)}"
        )

    catalog_digest = proposal.get("catalog_digest")
    if not isinstance(catalog_digest, str) or not HEX_64_REGEX.match(catalog_digest):
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: catalog_digest must be lowercase 64-char hex SHA-256")

    # Hard locks validation
    hard_locks = proposal.get("hard_locks")
    if not isinstance(hard_locks, list) or len(hard_locks) != 5:
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: hard_locks must be a list of exactly 5 entries")

    hl_map: Dict[str, str] = {}
    hl_paths: List[str] = []
    allowed_hl_keys = {"package_path", "revision"}
    for idx, hl in enumerate(hard_locks):
        if not isinstance(hl, dict):
            raise TypeError(f"INVALID_LOCK_PROPOSAL_V2: hard_locks[{idx}] must be a dict")
        if set(hl.keys()) != allowed_hl_keys:
            raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: hard_locks[{idx}] has invalid keys")
        path = hl.get("package_path")
        rev = hl.get("revision")
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: Invalid package_path in hard_locks[{idx}]")
        if not isinstance(rev, str) or not rev.strip():
            raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: Invalid revision in hard_locks[{idx}]")
        if path in hl_map:
            raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: Duplicate package_path {path!r} in hard_locks")
        hl_map[path] = rev.strip()
        hl_paths.append(path)

    expected_set = set(HARD_LOCK_PACKAGES)
    if set(hl_map.keys()) != expected_set:
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: hard_locks packages do not match HARD_LOCK_PACKAGES")
    if hl_paths != sorted(expected_set):
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: hard_locks must be sorted lexicographically by package_path")

    # Reconstruct catalog payload from hard_locks and verify against catalog_digest
    reconstructed_cat_payload = {
        "channel": 0,
        "contract": CONTRACT_CATALOG_DIGEST_PAYLOAD,
        "packages": [
            {"catalog_revision": hl_map[p], "package_path": p}
            for p in sorted(expected_set)
        ],
    }
    reconstructed_cat_digest = hash_canonical_json_v1(reconstructed_cat_payload)
    if reconstructed_cat_digest != catalog_digest:
        raise ValueError(
            f"INVALID_LOCK_PROPOSAL_V2: catalog_digest {catalog_digest!r} does not match hard_locks content {reconstructed_cat_digest!r}"
        )

    # Environment validation
    environment = proposal.get("environment")
    if not isinstance(environment, dict):
        raise TypeError("INVALID_LOCK_PROPOSAL_V2: environment must be a dictionary")
    _validate_no_local_paths(environment, "environment")

    if set(environment.keys()) != ALLOWED_ENVIRONMENT_KEYS:
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: environment keys mismatch")

    jdk_major = environment.get("jdk_major")
    if not isinstance(jdk_major, int) or jdk_major != 17 or isinstance(jdk_major, bool):
        raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: environment.jdk_major must be integer 17, got {jdk_major!r}")

    for k in ["cmdline_tools_revision", "emulator_revision", "runner_image_label", "runner_image_version", "runner_os"]:
        v = environment.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: environment.{k} must be a non-empty string")

    # Provenance V2 validation (binds both catalog and GPU runs)
    provenance = proposal.get("provenance")
    if not isinstance(provenance, dict):
        raise TypeError("INVALID_LOCK_PROPOSAL_V2: provenance must be a dictionary")
    _validate_no_local_paths(provenance, "provenance")

    if set(provenance.keys()) != ALLOWED_PROVENANCE_V2_KEYS:
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: provenance keys mismatch")

    for k in ALLOWED_PROVENANCE_V2_KEYS:
        v = provenance.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: provenance.{k} must be a non-empty string")

    if not COMMIT_SHA_40_REGEX.match(provenance["catalog_commit_sha"]):
        raise ValueError(
            "INVALID_LOCK_PROPOSAL_V2: provenance.catalog_commit_sha must be exactly 40 lowercase hex characters"
        )
    if not CATALOG_RUN_ID_REGEX.match(provenance["catalog_run_id"]):
        raise ValueError(
            "INVALID_LOCK_PROPOSAL_V2: provenance.catalog_run_id must be a positive decimal integer string"
        )
    if not COMMIT_SHA_40_REGEX.match(provenance["gpu_commit_sha"]):
        raise ValueError(
            "INVALID_LOCK_PROPOSAL_V2: provenance.gpu_commit_sha must be exactly 40 lowercase hex characters"
        )
    if not CATALOG_RUN_ID_REGEX.match(provenance["gpu_run_id"]):
        raise ValueError(
            "INVALID_LOCK_PROPOSAL_V2: provenance.gpu_run_id must be a positive decimal integer string"
        )

    # Environment / Provenance coherence
    if environment["runner_image_label"].strip() != provenance["runner_image_label"].strip():
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: runner_image_label mismatch between environment and provenance")
    if environment["runner_image_version"].strip() != provenance["runner_image_version"].strip():
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: runner_image_version mismatch between environment and provenance")

    # Freshness validation
    freshness = proposal.get("freshness")
    if not isinstance(freshness, dict):
        raise TypeError("INVALID_LOCK_PROPOSAL_V2: freshness must be a dictionary")

    if set(freshness.keys()) != ALLOWED_FRESHNESS_KEYS:
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: freshness keys mismatch")

    observed_at = freshness.get("observed_at")
    fresh_until = freshness.get("fresh_until")
    max_age_days = freshness.get("max_age_days")

    if not isinstance(observed_at, str) or not isinstance(fresh_until, str):
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: observed_at and fresh_until must be strings")
    if not isinstance(max_age_days, int) or max_age_days != MAX_FRESHNESS_DAYS or isinstance(max_age_days, bool):
        raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: max_age_days must be integer {MAX_FRESHNESS_DAYS}")

    validate_canonical_timestamp(observed_at)
    validate_canonical_timestamp(fresh_until)

    dt_obs = datetime.datetime.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ")
    dt_fresh = datetime.datetime.strptime(fresh_until, "%Y-%m-%dT%H:%M:%SZ")
    if dt_fresh <= dt_obs:
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: fresh_until must be strictly greater than observed_at")
    delta = dt_fresh - dt_obs
    if delta.days != MAX_FRESHNESS_DAYS or delta.seconds != 0:
        raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: fresh_until must be exactly {MAX_FRESHNESS_DAYS} days after observed_at")

    # GPU Evidence validation
    gpu_evidence = proposal.get("gpu_evidence")
    if not isinstance(gpu_evidence, dict):
        raise TypeError("INVALID_LOCK_PROPOSAL_V2: gpu_evidence must be a dictionary")
    _validate_no_local_paths(gpu_evidence, "gpu_evidence")

    for prohibited in ["selected_gpu", "gpu_mode", "default_gpu"]:
        if prohibited in gpu_evidence:
            raise ValueError(f"GPU_SELECTION_PROHIBITED_IN_PROPOSAL: {prohibited!r} found in gpu_evidence")

    if set(gpu_evidence.keys()) != ALLOWED_GPU_EVIDENCE_KEYS:
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: gpu_evidence keys mismatch")

    gpu_status = gpu_evidence.get("status")
    if gpu_status not in ALLOWED_GPU_STATUSES:
        raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: gpu_evidence.status invalid: {gpu_status!r}")

    parser_status = gpu_evidence.get("parser_status")
    if parser_status not in ALLOWED_GPU_PARSER_STATUSES:
        raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: gpu_evidence.parser_status invalid: {parser_status!r}")

    evidence_ready = gpu_evidence.get("evidence_ready")
    if not isinstance(evidence_ready, bool):
        raise TypeError("INVALID_LOCK_PROPOSAL_V2: gpu_evidence.evidence_ready must be a boolean")

    candidates_raw = gpu_evidence.get("candidate_modes")
    if not isinstance(candidates_raw, list):
        raise TypeError("INVALID_LOCK_PROPOSAL_V2: gpu_evidence.candidate_modes must be a list")
    for m in candidates_raw:
        if not isinstance(m, str) or not m.strip():
            raise ValueError("INVALID_LOCK_PROPOSAL_V2: candidate_modes items must be non-empty strings")
    if candidates_raw != sorted(list(set(candidates_raw))):
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: candidate_modes must be sorted and deduplicated")

    gpu_emu_rev = gpu_evidence.get("emulator_revision")
    if not isinstance(gpu_emu_rev, str) or not gpu_emu_rev.strip():
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: gpu_evidence.emulator_revision must be non-empty string")

    projection_sha256 = gpu_evidence.get("projection_sha256")
    if not isinstance(projection_sha256, str):
        raise ValueError("INVALID_LOCK_PROPOSAL_V2: gpu_evidence.projection_sha256 must be a string")

    # Tripartite emulator revision binding
    env_emu_rev = environment["emulator_revision"].strip()
    hl_emu_rev = hl_map["emulator"]
    if gpu_emu_rev.strip() != env_emu_rev:
        raise ValueError(
            f"INVALID_LOCK_PROPOSAL_V2: gpu_evidence.emulator_revision ({gpu_emu_rev!r}) != environment.emulator_revision ({env_emu_rev!r})"
        )
    if env_emu_rev != hl_emu_rev:
        raise ValueError(
            f"INVALID_LOCK_PROPOSAL_V2: environment.emulator_revision ({env_emu_rev!r}) != hard_locks['emulator'] ({hl_emu_rev!r})"
        )

    if evidence_ready is True:
        if gpu_status != "PASS_STRICT":
            raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: evidence_ready=True requires status='PASS_STRICT', got {gpu_status!r}")
        if parser_status != "PASS_STRICT":
            raise ValueError(f"INVALID_LOCK_PROPOSAL_V2: evidence_ready=True requires parser_status='PASS_STRICT', got {parser_status!r}")
        if len(candidates_raw) < 1:
            raise ValueError("INVALID_LOCK_PROPOSAL_V2: evidence_ready=True requires candidate_modes >= 1")
        if not HEX_64_REGEX.match(projection_sha256):
            raise ValueError(
                f"INVALID_LOCK_PROPOSAL_V2: evidence_ready=True requires valid projection_sha256 (64 hex chars), got {projection_sha256!r}"
            )
        if ready_for_review is not True:
            raise ValueError("INVALID_LOCK_PROPOSAL_V2: ready_for_human_review must be True when evidence_ready=True and all invariants pass")
    else:
        if ready_for_review is not False:
            raise ValueError("INVALID_LOCK_PROPOSAL_V2: ready_for_human_review must be False when evidence_ready=False")


def create_lock_proposal(
    catalog_digest_payload: Dict[str, Any],
    environment: Dict[str, Any],
    gpu_evidence: Dict[str, Any],
    freshness: Dict[str, Any],
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Constructs an immutable ALVORADA_LOCK_PROPOSAL_V1.
    Fails closed if any contractual invariants or extra semantic inputs are encountered.
    """
    # 1. Re-validate catalog digest payload directly (no trust-by-call-chain)
    validate_catalog_digest_payload(catalog_digest_payload)
    catalog_digest = hash_canonical_json_v1(catalog_digest_payload)

    # 2. Derive hard_locks strictly from catalog_digest_payload
    hard_locks = [
        {
            "package_path": p["package_path"],
            "revision": p["catalog_revision"],
        }
        for p in sorted(catalog_digest_payload["packages"], key=lambda x: x["package_path"])
    ]
    hl_map = {hl["package_path"]: hl["revision"] for hl in hard_locks}

    # 3. Validate environment (strictly closed schema: NO SILENTLY UNBOUND SEMANTIC INPUT)
    if not isinstance(environment, dict):
        raise TypeError("environment must be a dictionary")
    _validate_no_local_paths(environment, "environment")

    if set(environment.keys()) != ALLOWED_ENVIRONMENT_KEYS:
        extra = set(environment.keys()) - ALLOWED_ENVIRONMENT_KEYS
        missing = ALLOWED_ENVIRONMENT_KEYS - set(environment.keys())
        raise ValueError(
            f"INVALID_ENVIRONMENT: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )

    jdk_major = environment["jdk_major"]
    if not isinstance(jdk_major, int) or jdk_major != 17 or isinstance(jdk_major, bool):
        raise ValueError(f"environment.jdk_major must be integer 17, got {jdk_major!r}")

    for req_field in [
        "cmdline_tools_revision",
        "emulator_revision",
        "runner_os",
        "runner_image_label",
        "runner_image_version",
    ]:
        val = environment[req_field]
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"Missing or invalid environment field: {req_field}")

    # Check hard_locks emulator revision against environment
    if environment["emulator_revision"].strip() != hl_map["emulator"]:
        raise ValueError(
            f"environment.emulator_revision ({environment['emulator_revision']!r}) != hard_locks['emulator'] ({hl_map['emulator']!r})"
        )

    # 4. Validate provenance (strictly closed schema: NO SILENTLY UNBOUND SEMANTIC INPUT)
    if not isinstance(provenance, dict):
        raise TypeError("provenance must be a dictionary")
    _validate_no_local_paths(provenance, "provenance")

    if set(provenance.keys()) != ALLOWED_PROVENANCE_KEYS:
        extra = set(provenance.keys()) - ALLOWED_PROVENANCE_KEYS
        missing = ALLOWED_PROVENANCE_KEYS - set(provenance.keys())
        raise ValueError(
            f"INVALID_PROVENANCE: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )

    for req_field in ALLOWED_PROVENANCE_KEYS:
        val = provenance[req_field]
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"Missing or invalid provenance field: {req_field}")

    repo_sha = provenance["repository_commit_sha"]
    if not isinstance(repo_sha, str) or not COMMIT_SHA_40_REGEX.match(repo_sha):
        raise ValueError(
            f"provenance.repository_commit_sha must be exactly 40 lowercase hex characters, got {repo_sha!r}"
        )

    run_id = provenance["catalog_run_id"]
    if not isinstance(run_id, str) or not CATALOG_RUN_ID_REGEX.match(run_id):
        raise ValueError(
            f"provenance.catalog_run_id must be a positive decimal integer string without signs, decimals, or spaces, got {run_id!r}"
        )

    # Environment / Provenance runner image coherence
    if environment["runner_image_label"].strip() != provenance["runner_image_label"].strip():
        raise ValueError(
            f"runner_image_label mismatch: environment ({environment['runner_image_label']!r}) != provenance ({provenance['runner_image_label']!r})"
        )
    if environment["runner_image_version"].strip() != provenance["runner_image_version"].strip():
        raise ValueError(
            f"runner_image_version mismatch: environment ({environment['runner_image_version']!r}) != provenance ({provenance['runner_image_version']!r})"
        )

    # 5. Validate freshness (strictly closed schema: NO SILENTLY UNBOUND SEMANTIC INPUT)
    if not isinstance(freshness, dict):
        raise TypeError("freshness must be a dictionary")

    if set(freshness.keys()) != ALLOWED_FRESHNESS_KEYS:
        extra = set(freshness.keys()) - ALLOWED_FRESHNESS_KEYS
        missing = ALLOWED_FRESHNESS_KEYS - set(freshness.keys())
        raise ValueError(
            f"INVALID_FRESHNESS: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )

    observed_at = freshness["observed_at"]
    fresh_until = freshness["fresh_until"]
    max_age_days = freshness["max_age_days"]

    if not isinstance(observed_at, str) or not isinstance(fresh_until, str):
        raise ValueError("freshness timestamps must be strings")
    if not isinstance(max_age_days, int) or max_age_days != MAX_FRESHNESS_DAYS or isinstance(max_age_days, bool):
        raise ValueError(f"freshness.max_age_days must be integer {MAX_FRESHNESS_DAYS}")

    validate_canonical_timestamp(observed_at)
    validate_canonical_timestamp(fresh_until)

    dt_obs = datetime.datetime.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ")
    dt_fresh = datetime.datetime.strptime(fresh_until, "%Y-%m-%dT%H:%M:%SZ")

    if dt_fresh <= dt_obs:
        raise ValueError("fresh_until must be strictly greater than observed_at")

    delta = dt_fresh - dt_obs
    if delta.days != MAX_FRESHNESS_DAYS or delta.seconds != 0:
        raise ValueError(
            f"fresh_until must be exactly {MAX_FRESHNESS_DAYS} days after observed_at, got delta {delta}"
        )

    # 6. Validate GPU evidence (strictly closed schema: NO SILENTLY UNBOUND SEMANTIC INPUT)
    if not isinstance(gpu_evidence, dict):
        raise TypeError("gpu_evidence must be a dictionary")
    _validate_no_local_paths(gpu_evidence, "gpu_evidence")

    for prohibited in ["selected_gpu", "gpu_mode", "default_gpu"]:
        if prohibited in gpu_evidence:
            raise ValueError(
                f"GPU_SELECTION_PROHIBITED_IN_PROPOSAL: {prohibited!r} found in gpu_evidence"
            )

    if set(gpu_evidence.keys()) != ALLOWED_GPU_EVIDENCE_KEYS:
        extra = set(gpu_evidence.keys()) - ALLOWED_GPU_EVIDENCE_KEYS
        missing = ALLOWED_GPU_EVIDENCE_KEYS - set(gpu_evidence.keys())
        raise ValueError(
            f"INVALID_GPU_EVIDENCE: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )

    gpu_status = gpu_evidence["status"]
    if gpu_status not in ALLOWED_GPU_STATUSES:
        raise ValueError(f"gpu_evidence.status invalid: {gpu_status!r}")

    parser_status = gpu_evidence["parser_status"]
    if parser_status not in ALLOWED_GPU_PARSER_STATUSES:
        raise ValueError(f"gpu_evidence.parser_status invalid: {parser_status!r}")

    evidence_ready = gpu_evidence["evidence_ready"]
    if not isinstance(evidence_ready, bool):
        raise TypeError("gpu_evidence.evidence_ready must be a boolean")

    candidates_raw = gpu_evidence["candidate_modes"]
    if not isinstance(candidates_raw, (list, set)):
        raise TypeError("gpu_evidence.candidate_modes must be a list or set")
    candidate_modes = sorted(list(set(candidates_raw)))

    gpu_emu_rev = gpu_evidence["emulator_revision"]
    if not isinstance(gpu_emu_rev, str) or not gpu_emu_rev.strip():
        raise ValueError("gpu_evidence.emulator_revision must be a non-empty string")

    # GPU revision binding to environment
    if gpu_emu_rev.strip() != environment["emulator_revision"].strip():
        raise ValueError(
            f"gpu_evidence.emulator_revision ({gpu_emu_rev!r}) != environment.emulator_revision ({environment['emulator_revision']!r})"
        )

    projection_sha256 = gpu_evidence["projection_sha256"]
    if not isinstance(projection_sha256, str):
        raise ValueError("gpu_evidence.projection_sha256 must be a string")

    if evidence_ready:
        if gpu_status != "PASS_STRICT":
            raise ValueError(
                f"gpu_evidence.evidence_ready=True requires status='PASS_STRICT', got {gpu_status!r}"
            )
        if parser_status != "PASS_STRICT":
            raise ValueError(
                f"gpu_evidence.evidence_ready=True requires parser_status='PASS_STRICT', got {parser_status!r}"
            )
        if len(candidate_modes) < 1:
            raise ValueError("gpu_evidence.evidence_ready=True requires candidate_modes >= 1")
        if not HEX_64_REGEX.match(projection_sha256.strip()):
            raise ValueError(
                f"gpu_evidence.evidence_ready=True requires valid projection_sha256 (64 lowercase hex chars), got {projection_sha256!r}"
            )
        ready_for_human_review = True
    else:
        ready_for_human_review = False

    # Build canonical proposal payload
    proposal: Dict[str, Any] = {
        "catalog_digest": catalog_digest,
        "contract": CONTRACT_LOCK_PROPOSAL,
        "environment": {
            "cmdline_tools_revision": environment["cmdline_tools_revision"].strip(),
            "emulator_revision": environment["emulator_revision"].strip(),
            "jdk_major": 17,
            "runner_image_label": environment["runner_image_label"].strip(),
            "runner_image_version": environment["runner_image_version"].strip(),
            "runner_os": environment["runner_os"].strip(),
        },
        "freshness": {
            "fresh_until": fresh_until,
            "max_age_days": 7,
            "observed_at": observed_at,
        },
        "gpu_evidence": {
            "candidate_modes": candidate_modes,
            "emulator_revision": gpu_emu_rev.strip(),
            "evidence_ready": evidence_ready,
            "parser_status": parser_status.strip(),
            "projection_sha256": projection_sha256.strip(),
            "status": gpu_status.strip(),
        },
        "hard_locks": hard_locks,
        "proposal_state": PROPOSAL_STATE_PENDING,
        "provenance": {
            "catalog_run_id": run_id,
            "repository_commit_sha": repo_sha,
            "runner_image_label": provenance["runner_image_label"].strip(),
            "runner_image_version": provenance["runner_image_version"].strip(),
        },
        "ready_for_human_review": ready_for_human_review,
    }

    validate_lock_proposal(proposal)
    return proposal


def create_lock_proposal_v2(
    catalog_digest_payload: Dict[str, Any],
    environment: Dict[str, Any],
    gpu_evidence: Dict[str, Any],
    freshness: Dict[str, Any],
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Constructs an immutable ALVORADA_LOCK_PROPOSAL_V2.
    Fails closed if any contractual invariants or extra semantic inputs are encountered.
    """
    # 1. Re-validate catalog digest payload directly
    validate_catalog_digest_payload(catalog_digest_payload)
    catalog_digest = hash_canonical_json_v1(catalog_digest_payload)

    # 2. Derive hard_locks strictly from catalog_digest_payload
    hard_locks = [
        {
            "package_path": p["package_path"],
            "revision": p["catalog_revision"],
        }
        for p in sorted(catalog_digest_payload["packages"], key=lambda x: x["package_path"])
    ]
    hl_map = {hl["package_path"]: hl["revision"] for hl in hard_locks}

    # 3. Validate environment (strictly closed schema: NO SILENTLY UNBOUND SEMANTIC INPUT)
    if not isinstance(environment, dict):
        raise TypeError("environment must be a dictionary")
    _validate_no_local_paths(environment, "environment")

    if set(environment.keys()) != ALLOWED_ENVIRONMENT_KEYS:
        extra = set(environment.keys()) - ALLOWED_ENVIRONMENT_KEYS
        missing = ALLOWED_ENVIRONMENT_KEYS - set(environment.keys())
        raise ValueError(
            f"INVALID_ENVIRONMENT: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )

    jdk_major = environment["jdk_major"]
    if not isinstance(jdk_major, int) or jdk_major != 17 or isinstance(jdk_major, bool):
        raise ValueError(f"environment.jdk_major must be integer 17, got {jdk_major!r}")

    for req_field in [
        "cmdline_tools_revision",
        "emulator_revision",
        "runner_os",
        "runner_image_label",
        "runner_image_version",
    ]:
        val = environment[req_field]
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"Missing or invalid environment field: {req_field}")

    # Check hard_locks emulator revision against environment
    if environment["emulator_revision"].strip() != hl_map["emulator"]:
        raise ValueError(
            f"environment.emulator_revision ({environment['emulator_revision']!r}) != hard_locks['emulator'] ({hl_map['emulator']!r})"
        )

    # 4. Validate provenance V2 (strictly closed schema: NO SILENTLY UNBOUND SEMANTIC INPUT)
    if not isinstance(provenance, dict):
        raise TypeError("provenance must be a dictionary")
    _validate_no_local_paths(provenance, "provenance")

    if set(provenance.keys()) != ALLOWED_PROVENANCE_V2_KEYS:
        extra = set(provenance.keys()) - ALLOWED_PROVENANCE_V2_KEYS
        missing = ALLOWED_PROVENANCE_V2_KEYS - set(provenance.keys())
        raise ValueError(
            f"INVALID_PROVENANCE_V2: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )

    for req_field in ALLOWED_PROVENANCE_V2_KEYS:
        val = provenance[req_field]
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"Missing or invalid provenance field: {req_field}")

    if not COMMIT_SHA_40_REGEX.match(provenance["catalog_commit_sha"]):
        raise ValueError(
            f"provenance.catalog_commit_sha must be exactly 40 lowercase hex characters, got {provenance['catalog_commit_sha']!r}"
        )
    if not CATALOG_RUN_ID_REGEX.match(provenance["catalog_run_id"]):
        raise ValueError(
            f"provenance.catalog_run_id must be a positive decimal integer string without signs, decimals, or spaces, got {provenance['catalog_run_id']!r}"
        )
    if not COMMIT_SHA_40_REGEX.match(provenance["gpu_commit_sha"]):
        raise ValueError(
            f"provenance.gpu_commit_sha must be exactly 40 lowercase hex characters, got {provenance['gpu_commit_sha']!r}"
        )
    if not CATALOG_RUN_ID_REGEX.match(provenance["gpu_run_id"]):
        raise ValueError(
            f"provenance.gpu_run_id must be a positive decimal integer string without signs, decimals, or spaces, got {provenance['gpu_run_id']!r}"
        )

    # Environment / Provenance runner image coherence
    if environment["runner_image_label"].strip() != provenance["runner_image_label"].strip():
        raise ValueError(
            f"runner_image_label mismatch: environment ({environment['runner_image_label']!r}) != provenance ({provenance['runner_image_label']!r})"
        )
    if environment["runner_image_version"].strip() != provenance["runner_image_version"].strip():
        raise ValueError(
            f"runner_image_version mismatch: environment ({environment['runner_image_version']!r}) != provenance ({provenance['runner_image_version']!r})"
        )

    # 5. Validate freshness (strictly closed schema: NO SILENTLY UNBOUND SEMANTIC INPUT)
    if not isinstance(freshness, dict):
        raise TypeError("freshness must be a dictionary")

    if set(freshness.keys()) != ALLOWED_FRESHNESS_KEYS:
        extra = set(freshness.keys()) - ALLOWED_FRESHNESS_KEYS
        missing = ALLOWED_FRESHNESS_KEYS - set(freshness.keys())
        raise ValueError(
            f"INVALID_FRESHNESS: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )

    observed_at = freshness["observed_at"]
    fresh_until = freshness["fresh_until"]
    max_age_days = freshness["max_age_days"]

    if not isinstance(observed_at, str) or not isinstance(fresh_until, str):
        raise ValueError("freshness timestamps must be strings")
    if not isinstance(max_age_days, int) or max_age_days != MAX_FRESHNESS_DAYS or isinstance(max_age_days, bool):
        raise ValueError(f"freshness.max_age_days must be integer {MAX_FRESHNESS_DAYS}")

    validate_canonical_timestamp(observed_at)
    validate_canonical_timestamp(fresh_until)

    dt_obs = datetime.datetime.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ")
    dt_fresh = datetime.datetime.strptime(fresh_until, "%Y-%m-%dT%H:%M:%SZ")

    if dt_fresh <= dt_obs:
        raise ValueError("fresh_until must be strictly greater than observed_at")

    delta = dt_fresh - dt_obs
    if delta.days != MAX_FRESHNESS_DAYS or delta.seconds != 0:
        raise ValueError(
            f"fresh_until must be exactly {MAX_FRESHNESS_DAYS} days after observed_at, got delta {delta}"
        )

    # 6. Validate GPU evidence (strictly closed schema: NO SILENTLY UNBOUND SEMANTIC INPUT)
    if not isinstance(gpu_evidence, dict):
        raise TypeError("gpu_evidence must be a dictionary")
    _validate_no_local_paths(gpu_evidence, "gpu_evidence")

    for prohibited in ["selected_gpu", "gpu_mode", "default_gpu"]:
        if prohibited in gpu_evidence:
            raise ValueError(
                f"GPU_SELECTION_PROHIBITED_IN_PROPOSAL: {prohibited!r} found in gpu_evidence"
            )

    if set(gpu_evidence.keys()) != ALLOWED_GPU_EVIDENCE_KEYS:
        extra = set(gpu_evidence.keys()) - ALLOWED_GPU_EVIDENCE_KEYS
        missing = ALLOWED_GPU_EVIDENCE_KEYS - set(gpu_evidence.keys())
        raise ValueError(
            f"INVALID_GPU_EVIDENCE: Unexpected keys {sorted(extra)} or missing keys {sorted(missing)}"
        )

    gpu_status = gpu_evidence["status"]
    if gpu_status not in ALLOWED_GPU_STATUSES:
        raise ValueError(f"gpu_evidence.status invalid: {gpu_status!r}")

    parser_status = gpu_evidence["parser_status"]
    if parser_status not in ALLOWED_GPU_PARSER_STATUSES:
        raise ValueError(f"gpu_evidence.parser_status invalid: {parser_status!r}")

    evidence_ready = gpu_evidence["evidence_ready"]
    if not isinstance(evidence_ready, bool):
        raise TypeError("gpu_evidence.evidence_ready must be a boolean")

    candidates_raw = gpu_evidence["candidate_modes"]
    if not isinstance(candidates_raw, (list, set)):
        raise TypeError("gpu_evidence.candidate_modes must be a list or set")
    candidate_modes = sorted(list(set(candidates_raw)))

    gpu_emu_rev = gpu_evidence["emulator_revision"]
    if not isinstance(gpu_emu_rev, str) or not gpu_emu_rev.strip():
        raise ValueError("gpu_evidence.emulator_revision must be a non-empty string")

    # GPU revision binding to environment
    if gpu_emu_rev.strip() != environment["emulator_revision"].strip():
        raise ValueError(
            f"gpu_evidence.emulator_revision ({gpu_emu_rev!r}) != environment.emulator_revision ({environment['emulator_revision']!r})"
        )

    projection_sha256 = gpu_evidence["projection_sha256"]
    if not isinstance(projection_sha256, str):
        raise ValueError("gpu_evidence.projection_sha256 must be a string")

    if evidence_ready:
        if gpu_status != "PASS_STRICT":
            raise ValueError(
                f"gpu_evidence.evidence_ready=True requires status='PASS_STRICT', got {gpu_status!r}"
            )
        if parser_status != "PASS_STRICT":
            raise ValueError(
                f"gpu_evidence.evidence_ready=True requires parser_status='PASS_STRICT', got {parser_status!r}"
            )
        if len(candidate_modes) < 1:
            raise ValueError("gpu_evidence.evidence_ready=True requires candidate_modes >= 1")
        if not HEX_64_REGEX.match(projection_sha256.strip()):
            raise ValueError(
                f"gpu_evidence.evidence_ready=True requires valid projection_sha256 (64 lowercase hex chars), got {projection_sha256!r}"
            )
        ready_for_human_review = True
    else:
        ready_for_human_review = False

    proposal: Dict[str, Any] = {
        "catalog_digest": catalog_digest,
        "contract": CONTRACT_LOCK_PROPOSAL_V2,
        "environment": {
            "cmdline_tools_revision": environment["cmdline_tools_revision"].strip(),
            "emulator_revision": environment["emulator_revision"].strip(),
            "jdk_major": 17,
            "runner_image_label": environment["runner_image_label"].strip(),
            "runner_image_version": environment["runner_image_version"].strip(),
            "runner_os": environment["runner_os"].strip(),
        },
        "freshness": {
            "fresh_until": fresh_until,
            "max_age_days": 7,
            "observed_at": observed_at,
        },
        "gpu_evidence": {
            "candidate_modes": candidate_modes,
            "emulator_revision": gpu_emu_rev.strip(),
            "evidence_ready": evidence_ready,
            "parser_status": parser_status.strip(),
            "projection_sha256": projection_sha256.strip(),
            "status": gpu_status.strip(),
        },
        "hard_locks": hard_locks,
        "proposal_state": PROPOSAL_STATE_PENDING,
        "provenance": {
            "catalog_commit_sha": provenance["catalog_commit_sha"].strip(),
            "catalog_run_id": provenance["catalog_run_id"].strip(),
            "gpu_commit_sha": provenance["gpu_commit_sha"].strip(),
            "gpu_run_id": provenance["gpu_run_id"].strip(),
            "runner_image_label": provenance["runner_image_label"].strip(),
            "runner_image_version": provenance["runner_image_version"].strip(),
        },
        "ready_for_human_review": ready_for_human_review,
    }

    validate_lock_proposal_v2(proposal)
    return proposal


def build_lock_proposal_v2_from_provenance(
    catalog_digest_payload: Dict[str, Any],
    catalog_provenance: Dict[str, Any],
    gpu_evidence: Dict[str, Any],
    gpu_provenance: Dict[str, Any],
    gpu_projection: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Synthesizes ALVORADA_LOCK_PROPOSAL_V2 directly from verified catalog and GPU evidence artifacts.
    Enforces causal freshness: proposal_observed_at = max(catalog_observed_at, gpu_observed_at),
    fresh_until = proposal_observed_at + 7 days.
    Enforces cross-run provenance coherence, projection binding, and tripartite emulator alignment.
    Fails closed if any invariant is violated.
    """
    # 1. Verify catalog artifacts
    validate_catalog_digest_payload(catalog_digest_payload)
    computed_cat_digest = hash_canonical_json_v1(catalog_digest_payload)
    validate_catalog_provenance(catalog_provenance)
    if catalog_provenance["catalog_digest"] != computed_cat_digest:
        raise ValueError(
            f"CATALOG_DIGEST_MISMATCH: provenance has {catalog_provenance['catalog_digest']!r}, payload computes {computed_cat_digest!r}"
        )

    # 2. Verify GPU projection and provenance
    validate_gpu_projection(gpu_projection)
    computed_gpu_proj_sha = compute_gpu_projection_sha256(gpu_projection)
    validate_gpu_provenance(gpu_provenance)
    if gpu_provenance["gpu_projection_sha256"] != computed_gpu_proj_sha:
        raise ValueError(
            f"GPU_PROJECTION_SHA_MISMATCH: provenance has {gpu_provenance['gpu_projection_sha256']!r}, projection computes {computed_gpu_proj_sha!r}"
        )
    if gpu_evidence.get("projection_sha256") != computed_gpu_proj_sha:
        raise ValueError(
            f"GPU_EVIDENCE_PROJECTION_MISMATCH: evidence has {gpu_evidence.get('projection_sha256')!r}, projection computes {computed_gpu_proj_sha!r}"
        )
    if gpu_evidence.get("candidate_modes") != gpu_projection.get("candidate_modes"):
        raise ValueError(
            f"GPU_CANDIDATE_MODES_MISMATCH: evidence has {gpu_evidence.get('candidate_modes')!r}, projection has {gpu_projection.get('candidate_modes')!r}"
        )

    # 3. Cross-run runner coherence
    if catalog_provenance["runner_image_label"] != gpu_provenance["runner_image_label"]:
        raise ValueError(
            f"CROSS_RUN_RUNNER_LABEL_MISMATCH: catalog={catalog_provenance['runner_image_label']!r}, gpu={gpu_provenance['runner_image_label']!r}"
        )
    if catalog_provenance["runner_image_version"] != gpu_provenance["runner_image_version"]:
        raise ValueError(
            f"CROSS_RUN_RUNNER_VERSION_MISMATCH: catalog={catalog_provenance['runner_image_version']!r}, gpu={gpu_provenance['runner_image_version']!r}"
        )
    if catalog_provenance["runner_os"] != gpu_provenance["runner_os"]:
        raise ValueError(
            f"CROSS_RUN_RUNNER_OS_MISMATCH: catalog={catalog_provenance['runner_os']!r}, gpu={gpu_provenance['runner_os']!r}"
        )

    # 4. Tripartite emulator revision alignment
    hl_emu = next(p["catalog_revision"] for p in catalog_digest_payload["packages"] if p["package_path"] == "emulator")
    if hl_emu != gpu_provenance["emulator_revision"]:
        raise ValueError(
            f"EMULATOR_REVISION_MISMATCH: catalog hard lock has {hl_emu!r}, gpu provenance has {gpu_provenance['emulator_revision']!r}"
        )
    if hl_emu != gpu_projection["emulator_revision"]:
        raise ValueError(
            f"EMULATOR_REVISION_MISMATCH: catalog hard lock has {hl_emu!r}, gpu projection has {gpu_projection['emulator_revision']!r}"
        )
    if hl_emu != gpu_evidence.get("emulator_revision"):
        raise ValueError(
            f"EMULATOR_REVISION_MISMATCH: catalog hard lock has {hl_emu!r}, gpu evidence has {gpu_evidence.get('emulator_revision')!r}"
        )

    # 5. Causal freshness calculation
    cat_dt = datetime.datetime.strptime(catalog_provenance["observed_at"], "%Y-%m-%dT%H:%M:%SZ")
    gpu_dt = datetime.datetime.strptime(gpu_provenance["observed_at"], "%Y-%m-%dT%H:%M:%SZ")
    proposal_dt = max(cat_dt, gpu_dt)
    proposal_obs = proposal_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_until_dt = proposal_dt + datetime.timedelta(days=7)
    fresh_until = fresh_until_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    freshness = {
        "fresh_until": fresh_until,
        "max_age_days": 7,
        "observed_at": proposal_obs,
    }

    environment = {
        "cmdline_tools_revision": catalog_provenance["cmdline_tools_revision"],
        "emulator_revision": hl_emu,
        "jdk_major": 17,
        "runner_image_label": catalog_provenance["runner_image_label"],
        "runner_image_version": catalog_provenance["runner_image_version"],
        "runner_os": catalog_provenance["runner_os"],
    }

    provenance = {
        "catalog_commit_sha": catalog_provenance["repository_commit_sha"],
        "catalog_run_id": catalog_provenance["run_id"],
        "gpu_commit_sha": gpu_provenance["repository_commit_sha"],
        "gpu_run_id": gpu_provenance["run_id"],
        "runner_image_label": catalog_provenance["runner_image_label"],
        "runner_image_version": catalog_provenance["runner_image_version"],
    }

    return create_lock_proposal_v2(
        catalog_digest_payload=catalog_digest_payload,
        environment=environment,
        gpu_evidence=gpu_evidence,
        freshness=freshness,
        provenance=provenance,
    )


def compute_lock_proposal_digest(proposal: Dict[str, Any]) -> str:
    """Computes LOCK_PROPOSAL_DIGEST over validated ALVORADA_LOCK_PROPOSAL (V1 or V2) payload."""
    validate_lock_proposal(proposal)
    return hash_canonical_json_v1(proposal)


# -----------------------------------------------------------------------------
# 3. HUMAN LOCK DECISION OBJECT & STRUCTURAL VERIFIER
# -----------------------------------------------------------------------------

def verify_human_decision(
    decision_obj: Dict[str, Any],
    proposal: Dict[str, Any],
    evaluation_time_utc: str,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Structurally verifies an externally supplied HumanDecision object against an immutable proposal.
    IMPORTANT:
    The existence of a valid decision object DOES NOT prove human identity or authorization.
    This function verifies schema, digests, candidate match, dual-window freshness, and temporal causality.
    Always returns report with HUMAN_AUTHORITY_EXTERNALLY_REQUIRED = True.
    """
    errors: List[str] = []
    report: Dict[str, Any] = {
        "HUMAN_AUTHORITY_EXTERNALLY_REQUIRED": True,
        "SCHEMA_VALID": False,
        "REFERENCES_MATCH": False,
        "SELECTED_GPU_VALID": False,
        "REVIEW_TIME_VALID": False,
        "EVALUATION_TIME_VALID": False,
        "DECISION_PRECEDES_OR_EQUALS_EVALUATION": False,
        "FRESHNESS_VALID": False,
    }

    # 1. Validate proposal structure first
    try:
        validate_lock_proposal(proposal)
    except Exception as e:
        return False, [f"INVALID_PROPOSAL: {e}"], report

    # 2. Closed schema for HumanDecision
    if not isinstance(decision_obj, dict):
        return False, ["Decision object must be a dictionary"], report

    extra_keys = set(decision_obj.keys()) - ALLOWED_HUMAN_DECISION_KEYS
    if extra_keys:
        errors.append(f"Unexpected field(s) in HumanDecision: {sorted(extra_keys)}")

    if decision_obj.get("contract") != CONTRACT_HUMAN_DECISION:
        errors.append(f"Invalid contract: {decision_obj.get('contract')!r}")

    # Verify review_context (mandatory non-empty dict, does NOT authenticate human)
    if "review_context" not in decision_obj:
        errors.append("Missing review_context in HumanDecision")
    else:
        review_context = decision_obj.get("review_context")
        if not isinstance(review_context, dict) or len(review_context) == 0:
            errors.append("review_context must be a non-empty dictionary")

    expected_prop_digest = compute_lock_proposal_digest(proposal)
    actual_prop_digest = decision_obj.get("proposal_digest")
    if actual_prop_digest != expected_prop_digest:
        errors.append(
            f"proposal_digest mismatch: {actual_prop_digest!r} != {expected_prop_digest!r}"
        )

    expected_cat_digest = proposal.get("catalog_digest")
    actual_cat_digest = decision_obj.get("catalog_digest")
    if actual_cat_digest != expected_cat_digest:
        errors.append(
            f"catalog_digest mismatch: {actual_cat_digest!r} != {expected_cat_digest!r}"
        )

    if not errors:
        report["REFERENCES_MATCH"] = True

    decision = decision_obj.get("decision")
    if decision not in ["APPROVE", "REJECT"]:
        errors.append(f"Invalid decision: {decision!r}, must be 'APPROVE' or 'REJECT'")

    selected_gpu = decision_obj.get("selected_gpu")
    candidate_modes = proposal.get("gpu_evidence", {}).get("candidate_modes", [])
    ready_for_review = proposal.get("ready_for_human_review", False)

    if decision == "APPROVE":
        if ready_for_review is not True:
            errors.append("Cannot approve proposal whose ready_for_human_review is False")
        if not selected_gpu or not isinstance(selected_gpu, str):
            errors.append("selected_gpu is mandatory for decision='APPROVE'")
        elif selected_gpu not in candidate_modes:
            errors.append(
                f"selected_gpu {selected_gpu!r} is not in proposal candidate_modes: {candidate_modes}"
            )
        else:
            if ready_for_review is True:
                report["SELECTED_GPU_VALID"] = True
    elif decision == "REJECT":
        if selected_gpu is not None:
            errors.append("selected_gpu must be None or omitted when decision='REJECT'")
        else:
            report["SELECTED_GPU_VALID"] = True

    # 3. Dual-window Freshness and Temporal Causality validation
    observed_at = proposal.get("freshness", {}).get("observed_at")
    fresh_until = proposal.get("freshness", {}).get("fresh_until")

    dt_obs = datetime.datetime.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ")
    dt_fresh = datetime.datetime.strptime(fresh_until, "%Y-%m-%dT%H:%M:%SZ")

    dt_review: Optional[datetime.datetime] = None
    dt_eval: Optional[datetime.datetime] = None

    # A. reviewed_at
    reviewed_at = decision_obj.get("reviewed_at")
    if not reviewed_at or not isinstance(reviewed_at, str):
        errors.append("Missing reviewed_at timestamp")
    else:
        try:
            validate_canonical_timestamp(reviewed_at)
            dt_review = datetime.datetime.strptime(reviewed_at, "%Y-%m-%dT%H:%M:%SZ")
            if dt_review > dt_fresh:
                errors.append(f"Proposal expired at review time: reviewed_at ({reviewed_at}) > fresh_until ({fresh_until})")
            elif dt_review < dt_obs:
                errors.append(f"Review predates observation: reviewed_at ({reviewed_at}) < observed_at ({observed_at})")
            else:
                report["REVIEW_TIME_VALID"] = True
        except Exception as e:
            errors.append(f"Invalid reviewed_at timestamp: {e}")

    # B. evaluation_time_utc
    if not evaluation_time_utc or not isinstance(evaluation_time_utc, str):
        errors.append("Missing or invalid evaluation_time_utc")
    else:
        try:
            validate_canonical_timestamp(evaluation_time_utc)
            dt_eval = datetime.datetime.strptime(evaluation_time_utc, "%Y-%m-%dT%H:%M:%SZ")
            if dt_eval > dt_fresh:
                errors.append(f"Proposal expired at evaluation time: evaluation_time_utc ({evaluation_time_utc}) > fresh_until ({fresh_until})")
            elif dt_eval < dt_obs:
                errors.append(f"Evaluation time predates observation: evaluation_time_utc ({evaluation_time_utc}) < observed_at ({observed_at})")
            else:
                report["EVALUATION_TIME_VALID"] = True
        except Exception as e:
            errors.append(f"Invalid evaluation_time_utc timestamp: {e}")

    # C. Temporal Causality: reviewed_at <= evaluation_time_utc
    if dt_review is not None and dt_eval is not None:
        if dt_review > dt_eval:
            errors.append(
                f"Decision in future: reviewed_at ({reviewed_at}) > evaluation_time_utc ({evaluation_time_utc})"
            )
        else:
            report["DECISION_PRECEDES_OR_EQUALS_EVALUATION"] = True

    report["FRESHNESS_VALID"] = (
        report["REVIEW_TIME_VALID"]
        and report["EVALUATION_TIME_VALID"]
        and report["DECISION_PRECEDES_OR_EQUALS_EVALUATION"]
    )
    report["SCHEMA_VALID"] = (len(errors) == 0)

    is_valid = (
        report["SCHEMA_VALID"]
        and report["REFERENCES_MATCH"]
        and report["SELECTED_GPU_VALID"]
        and report["FRESHNESS_VALID"]
    )
    return is_valid, errors, report


# -----------------------------------------------------------------------------
# 4. LOCK DIGEST & LOCK CANDIDATE COMPUTATION
# -----------------------------------------------------------------------------

def compute_lock_candidate(
    proposal: Dict[str, Any],
    human_decision: Dict[str, Any],
    evaluation_time_utc: str,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]], List[str]]:
    """
    Purely computational function constructing the final ALVORADA_LOCK_PAYLOAD_V1
    from an immutable proposal and a structurally verified HumanDecision object.
    NOTE:
    Does NOT declare the lock approved by human authority.
    Returns:
    (is_valid, LOCK_DIGEST, lock_payload, errors)
    Status: LOCK_CANDIDATE_COMPUTED
    """
    try:
        validate_lock_proposal(proposal)
    except Exception as e:
        return False, None, None, [f"INVALID_PROPOSAL: {e}"]

    is_valid_decision, errors, report = verify_human_decision(human_decision, proposal, evaluation_time_utc)
    if not is_valid_decision:
        return False, None, None, [f"HUMAN_DECISION_INVALID: {err}" for err in errors]

    if human_decision.get("decision") != "APPROVE":
        return False, None, None, ["DECISION_IS_NOT_APPROVE: Cannot compute lock candidate for rejected proposal"]

    if proposal.get("ready_for_human_review") is not True:
        return False, None, None, ["PROPOSAL_NOT_READY_FOR_HUMAN_REVIEW: Cannot compute lock candidate"]

    selected_gpu = human_decision["selected_gpu"]

    lock_payload: Dict[str, Any] = {
        "catalog_digest": proposal["catalog_digest"],
        "contract": CONTRACT_LOCK_PAYLOAD,
        "environment_locks": {
            "emulator_revision": proposal["environment"]["emulator_revision"],
            "jdk_major": 17,
        },
        "hard_locks": proposal["hard_locks"],
        "proposal_digest": compute_lock_proposal_digest(proposal),
        "selected_gpu": selected_gpu,
    }

    lock_digest = hash_canonical_json_v1(lock_payload)
    return True, lock_digest, lock_payload, []
