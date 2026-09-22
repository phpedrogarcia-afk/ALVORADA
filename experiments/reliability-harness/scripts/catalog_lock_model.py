#!/usr/bin/env python3
"""
ALVORADA — Three-Digest Catalog Lock Model & Immutable Lock Proposal Contract
Contract Version: RECOVERY-G1-002

Implements:
1. CATALOG_DIGEST: Cryptographic identity of pure stable catalog channel state
   for the 5 HARD_LOCK packages (ALVORADA_CATALOG_DIGEST_PAYLOAD_V1).
2. LOCK_PROPOSAL_DIGEST: Cryptographic identity of the immutable discovery proposal
   containing provenance, environment, freshness, and GPU evidence without human decision
   (ALVORADA_LOCK_PROPOSAL_V1).
3. LOCK_DIGEST: Cryptographic identity of the final lock payload produced only after
   a valid external human decision object selects a validated GPU candidate
   (ALVORADA_LOCK_PAYLOAD_V1).
4. Human Decision Contract & Structural Verifier (ALVORADA_HUMAN_LOCK_DECISION_V1).
   NOTE: Human authority is strictly external. The existence of a valid decision JSON
   does not constitute proof of human identity within the library.
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
CONTRACT_HUMAN_DECISION = "ALVORADA_HUMAN_LOCK_DECISION_V1"
CONTRACT_LOCK_PAYLOAD = "ALVORADA_LOCK_PAYLOAD_V1"

PROPOSAL_STATE_PENDING = "PENDING_HUMAN_REVIEW"
MAX_FRESHNESS_DAYS = 7


# -----------------------------------------------------------------------------
# 1. CATALOG DIGEST GENERATION & PRE-CONDITIONS
# -----------------------------------------------------------------------------

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

    return {
        "channel": 0,
        "contract": CONTRACT_CATALOG_DIGEST_PAYLOAD,
        "packages": sorted_packages,
    }


def compute_catalog_digest(projection: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Validates projection pre-conditions and returns (CATALOG_DIGEST, catalog_payload).
    """
    payload = create_catalog_digest_payload(projection)
    digest = hash_canonical_json_v1(payload)
    return digest, payload


# -----------------------------------------------------------------------------
# 2. IMMUTABLE LOCK PROPOSAL
# -----------------------------------------------------------------------------

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


def create_lock_proposal(
    catalog_digest_payload: Dict[str, Any],
    environment: Dict[str, Any],
    gpu_evidence: Dict[str, Any],
    freshness: Dict[str, Any],
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Constructs an immutable ALVORADA_LOCK_PROPOSAL_V1.
    Fails closed if any contractual invariants are violated.
    """
    # 1. Validate catalog digest payload
    if catalog_digest_payload.get("contract") != CONTRACT_CATALOG_DIGEST_PAYLOAD:
        raise ValueError("Invalid catalog_digest_payload contract")
    cat_packages = catalog_digest_payload.get("packages", [])
    if len(cat_packages) != 5:
        raise ValueError("catalog_digest_payload must contain exactly 5 packages")

    catalog_digest = hash_canonical_json_v1(catalog_digest_payload)

    # 2. Derive hard_locks strictly from catalog_digest_payload
    hard_locks = [
        {
            "package_path": p["package_path"],
            "revision": p["catalog_revision"],
        }
        for p in sorted(cat_packages, key=lambda x: x["package_path"])
    ]

    # 3. Validate environment
    if not isinstance(environment, dict):
        raise TypeError("environment must be a dictionary")
    _validate_no_local_paths(environment, "environment")

    jdk_major = environment.get("jdk_major")
    if not isinstance(jdk_major, int) or jdk_major != 17:
        raise ValueError(f"environment.jdk_major must be integer 17, got {jdk_major!r}")

    for req_field in [
        "cmdline_tools_revision",
        "emulator_revision",
        "runner_os",
        "runner_image_label",
        "runner_image_version",
    ]:
        val = environment.get(req_field)
        if not val or not isinstance(val, str) or not val.strip():
            raise ValueError(f"Missing or invalid environment field: {req_field}")

    # 4. Validate GPU evidence (strictly NO GPU selection)
    if not isinstance(gpu_evidence, dict):
        raise TypeError("gpu_evidence must be a dictionary")
    for prohibited in ["selected_gpu", "gpu_mode", "default_gpu"]:
        if prohibited in gpu_evidence:
            raise ValueError(
                f"GPU_SELECTION_PROHIBITED_IN_PROPOSAL: {prohibited!r} found in gpu_evidence"
            )

    candidates_raw = gpu_evidence.get("candidate_modes")
    if not isinstance(candidates_raw, (list, set)):
        raise TypeError("gpu_evidence.candidate_modes must be a list or set")
    candidate_modes = sorted(list(set(candidates_raw)))

    evidence_ready = gpu_evidence.get("evidence_ready")
    if not isinstance(evidence_ready, bool):
        raise TypeError("gpu_evidence.evidence_ready must be a boolean")

    parser_status = gpu_evidence.get("parser_status")
    if not parser_status or not isinstance(parser_status, str):
        raise ValueError("Missing or invalid gpu_evidence.parser_status")

    if evidence_ready:
        if len(candidate_modes) < 1:
            raise ValueError("gpu_evidence.evidence_ready=True requires candidate_modes >= 1")
        if parser_status != "PASS_STRICT":
            raise ValueError(
                f"gpu_evidence.evidence_ready=True requires parser_status='PASS_STRICT', got {parser_status!r}"
            )

    # 5. Validate freshness
    if not isinstance(freshness, dict):
        raise TypeError("freshness must be a dictionary")
    observed_at = freshness.get("observed_at")
    fresh_until = freshness.get("fresh_until")
    max_age_days = freshness.get("max_age_days")

    if not observed_at or not isinstance(observed_at, str):
        raise ValueError("Missing freshness.observed_at")
    if not fresh_until or not isinstance(fresh_until, str):
        raise ValueError("Missing freshness.fresh_until")
    if not isinstance(max_age_days, int) or max_age_days != MAX_FRESHNESS_DAYS:
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

    # 6. Validate provenance
    if not isinstance(provenance, dict):
        raise TypeError("provenance must be a dictionary")
    _validate_no_local_paths(provenance, "provenance")

    for req_field in [
        "repository_commit_sha",
        "catalog_run_id",
        "runner_image_label",
        "runner_image_version",
    ]:
        val = provenance.get(req_field)
        if not val or not isinstance(val, str) or not val.strip():
            raise ValueError(f"Missing or invalid provenance field: {req_field}")

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
            "emulator_revision": gpu_evidence.get("emulator_revision", environment["emulator_revision"]).strip(),
            "evidence_ready": evidence_ready,
            "parser_status": parser_status.strip(),
            "projection_sha256": gpu_evidence.get("projection_sha256", "").strip(),
            "status": gpu_evidence.get("status", "PASS_STRICT").strip(),
        },
        "hard_locks": hard_locks,
        "proposal_state": PROPOSAL_STATE_PENDING,
        "provenance": {
            "catalog_run_id": provenance["catalog_run_id"].strip(),
            "repository_commit_sha": provenance["repository_commit_sha"].strip(),
            "runner_image_label": provenance["runner_image_label"].strip(),
            "runner_image_version": provenance["runner_image_version"].strip(),
        },
    }

    return proposal


def compute_lock_proposal_digest(proposal: Dict[str, Any]) -> str:
    """Computes LOCK_PROPOSAL_DIGEST over ALVORADA_LOCK_PROPOSAL_V1 payload."""
    if proposal.get("contract") != CONTRACT_LOCK_PROPOSAL:
        raise ValueError(f"Invalid proposal contract: {proposal.get('contract')!r}")
    if proposal.get("proposal_state") != PROPOSAL_STATE_PENDING:
        raise ValueError(
            f"Proposal state must be {PROPOSAL_STATE_PENDING!r}, got {proposal.get('proposal_state')!r}"
        )
    return hash_canonical_json_v1(proposal)


# -----------------------------------------------------------------------------
# 3. HUMAN LOCK DECISION OBJECT & STRUCTURAL VERIFIER
# -----------------------------------------------------------------------------

def verify_human_decision(
    decision_obj: Dict[str, Any],
    proposal: Dict[str, Any],
    current_time_utc: Optional[str] = None,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Structurally verifies an externally supplied HumanDecision object against an immutable proposal.
    IMPORTANT:
    The existence of a valid decision object DOES NOT prove human identity or authorization.
    This function verifies schema, digests, candidate match, and freshness only.
    Always returns report with HUMAN_AUTHORITY_EXTERNALLY_REQUIRED = True.
    """
    errors: List[str] = []
    report: Dict[str, Any] = {
        "HUMAN_AUTHORITY_EXTERNALLY_REQUIRED": True,
        "SCHEMA_VALID": False,
        "REFERENCES_MATCH": False,
        "SELECTED_GPU_VALID": False,
        "FRESHNESS_VALID": False,
    }

    if not isinstance(decision_obj, dict):
        return False, ["Decision object must be a dictionary"], report

    if decision_obj.get("contract") != CONTRACT_HUMAN_DECISION:
        errors.append(f"Invalid contract: {decision_obj.get('contract')!r}")

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
    evidence_ready = proposal.get("gpu_evidence", {}).get("evidence_ready", False)
    parser_status = proposal.get("gpu_evidence", {}).get("parser_status", "")

    if decision == "APPROVE":
        if not selected_gpu or not isinstance(selected_gpu, str):
            errors.append("selected_gpu is mandatory for decision='APPROVE'")
        elif selected_gpu not in candidate_modes:
            errors.append(
                f"selected_gpu {selected_gpu!r} is not in proposal candidate_modes: {candidate_modes}"
            )
        elif not evidence_ready:
            errors.append("Cannot approve proposal whose gpu_evidence.evidence_ready is False")
        elif parser_status != "PASS_STRICT":
            errors.append(f"Cannot approve proposal whose parser_status is {parser_status!r}")
        else:
            report["SELECTED_GPU_VALID"] = True
    elif decision == "REJECT":
        if selected_gpu is not None:
            errors.append("selected_gpu must be None or omitted when decision='REJECT'")
        report["SELECTED_GPU_VALID"] = True

    reviewed_at = decision_obj.get("reviewed_at")
    if not reviewed_at or not isinstance(reviewed_at, str):
        errors.append("Missing reviewed_at timestamp")
    else:
        try:
            validate_canonical_timestamp(reviewed_at)
            dt_review = datetime.datetime.strptime(reviewed_at, "%Y-%m-%dT%H:%M:%SZ")
            fresh_until = proposal.get("freshness", {}).get("fresh_until")
            observed_at = proposal.get("freshness", {}).get("observed_at")
            if fresh_until and observed_at:
                dt_fresh = datetime.datetime.strptime(fresh_until, "%Y-%m-%dT%H:%M:%SZ")
                dt_obs = datetime.datetime.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ")
                if dt_review > dt_fresh:
                    errors.append(f"Proposal expired: reviewed_at ({reviewed_at}) > fresh_until ({fresh_until})")
                elif dt_review < dt_obs:
                    errors.append(f"Review predates observation: reviewed_at ({reviewed_at}) < observed_at ({observed_at})")
                else:
                    report["FRESHNESS_VALID"] = True
        except Exception as e:
            errors.append(f"Invalid reviewed_at timestamp: {e}")

    report["SCHEMA_VALID"] = (len(errors) == 0)
    is_valid = report["SCHEMA_VALID"] and report["REFERENCES_MATCH"] and report["SELECTED_GPU_VALID"] and report["FRESHNESS_VALID"]
    return is_valid, errors, report


# -----------------------------------------------------------------------------
# 4. LOCK DIGEST & LOCK CANDIDATE COMPUTATION
# -----------------------------------------------------------------------------

def compute_lock_candidate(
    proposal: Dict[str, Any],
    human_decision: Dict[str, Any],
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
    is_valid_decision, errors, report = verify_human_decision(human_decision, proposal)
    if not is_valid_decision:
        return False, None, None, [f"HUMAN_DECISION_INVALID: {err}" for err in errors]

    if human_decision.get("decision") != "APPROVE":
        return False, None, None, ["DECISION_IS_NOT_APPROVE: Cannot compute lock candidate for rejected proposal"]

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
