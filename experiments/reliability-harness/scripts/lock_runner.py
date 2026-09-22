#!/usr/bin/env python3
"""
ALVORADA — Lock Generation & Decision Materialization Runner
Campaign: ALVORADA G1 POST-FOUNDER-APPROVAL EXECUTION CAMPAIGN 001

Materializes external founder human decision, validates it against Proposal V2,
computes ALVORADA_LOCK_PAYLOAD, and generates the first real LOCK_DIGEST.

Classification: APPROVED_EXPERIMENTAL_G1_LOCK
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
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
from catalog_lock_model import (
    CONTRACT_HUMAN_DECISION,
    CONTRACT_LOCK_PAYLOAD,
    compute_lock_candidate,
    compute_lock_proposal_digest,
    validate_lock_proposal,
    verify_human_decision,
)
from proposal_assembly_runner import verify_directory_checksums


EXTERNAL_FOUNDER_DECISION = {
    "contract": "ALVORADA_HUMAN_LOCK_DECISION_V1",
    "proposal_digest": "5517290ec9b90cdcbc13ad34a1228a1ff422f2a5c2326d622e9f2ae249b411b4",
    "catalog_digest": "e9148d7bcdb5124182f87787a78899845aa9a60aefbe5c4bc581539201b4f6ed",
    "decision": "APPROVE",
    "selected_gpu": "swiftshader",
    "reviewed_at": "2026-09-22T14:45:17Z",
    "review_context": {
        "authority_basis": "EXTERNAL_FOUNDER_GATE",
        "decision_statement": "Aprovo o lock com swiftshader.",
    },
}


def materialize_human_decision(
    output_dir: str,
    decision_data: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], str]:
    """Materializes external founder human decision into disk artifacts with checksums."""
    os.makedirs(output_dir, exist_ok=True)
    decision = decision_data or EXTERNAL_FOUNDER_DECISION

    # 1. Canonical JSON bytes
    decision_bytes = canonicalize_json_v1(decision)
    decision_digest = hashlib.sha256(decision_bytes).hexdigest()
    json_path = os.path.join(output_dir, "human-lock-decision.json")
    with open(json_path, "wb") as f:
        f.write(decision_bytes)

    # 2. Text audit report
    txt_lines = [
        "ALVORADA HUMAN LOCK DECISION AUDIT REPORT",
        "=========================================",
        "SOURCE_OF_AUTHORITY = EXTERNAL_FOUNDER_DECISION",
        "AGENT_DID_NOT_SELECT_GPU = TRUE",
        "",
        f"Contract:             {decision['contract']}",
        f"Decision:             {decision['decision']}",
        f"Selected GPU:         {decision.get('selected_gpu')}",
        f"Reviewed At UTC:      {decision['reviewed_at']}",
        f"Proposal Digest Ref:  {decision['proposal_digest']}",
        f"Catalog Digest Ref:   {decision['catalog_digest']}",
        f"Decision Digest SHA:  {decision_digest}",
        "",
        "REVIEW CONTEXT:",
        f"  Authority Basis:    {decision['review_context'].get('authority_basis')}",
        f"  Decision Statement: {decision['review_context'].get('decision_statement')}",
        "",
        "END OF HUMAN LOCK DECISION REPORT",
        "",
    ]
    txt_content = "\n".join(txt_lines)
    txt_bytes = txt_content.encode("utf-8")
    txt_sha = hashlib.sha256(txt_bytes).hexdigest()
    txt_path = os.path.join(output_dir, "human-lock-decision.txt")
    with open(txt_path, "wb") as f:
        f.write(txt_bytes)

    # 3. Checksums
    chk_content = (
        f"{decision_digest}  human-lock-decision.json\n"
        f"{txt_sha}  human-lock-decision.txt\n"
    )
    chk_path = os.path.join(output_dir, "checksums.sha256")
    with open(chk_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(chk_content)

    return decision, decision_digest


def materialize_lock_payload(
    output_dir: str,
    lock_payload: Dict[str, Any],
    lock_digest: str,
) -> Tuple[Dict[str, Any], str]:
    """Materializes computed lock payload into disk artifacts with checksums."""
    os.makedirs(output_dir, exist_ok=True)

    # 1. Canonical JSON bytes
    lock_bytes = canonicalize_json_v1(lock_payload)
    actual_digest = hashlib.sha256(lock_bytes).hexdigest()
    if actual_digest != lock_digest:
        raise ValueError(
            f"LOCK_DIGEST_MISMATCH: computed {actual_digest} != expected {lock_digest}"
        )

    json_path = os.path.join(output_dir, "lock.json")
    with open(json_path, "wb") as f:
        f.write(lock_bytes)

    # 2. Text audit report
    txt_lines = [
        "ALVORADA APPROVED EXPERIMENTAL LOCK REPORT",
        "==========================================",
        "CLASSIFICATION: APPROVED_EXPERIMENTAL_G1_LOCK",
        f"Contract:           {lock_payload['contract']}",
        f"LOCK_DIGEST:        {lock_digest}",
        f"Proposal Digest:    {lock_payload['proposal_digest']}",
        f"Catalog Digest:     {lock_payload['catalog_digest']}",
        f"Selected GPU Mode:  {lock_payload['selected_gpu']}",
        "",
        "LOCKED ENVIRONMENT:",
        f"  JDK Major Version:      {lock_payload['environment_locks']['jdk_major']}",
        f"  Emulator Revision:     {lock_payload['environment_locks']['emulator_revision']}",
        "",
        "HARD LOCKED PACKAGES (5):",
    ]
    for idx, pkg in enumerate(lock_payload["hard_locks"], 1):
        txt_lines.append(f"  {idx}. {pkg['package_path']} -> {pkg['revision']}")

    txt_lines.extend([
        "",
        "END OF APPROVED EXPERIMENTAL LOCK REPORT",
        "",
    ])
    txt_content = "\n".join(txt_lines)
    txt_bytes = txt_content.encode("utf-8")
    txt_sha = hashlib.sha256(txt_bytes).hexdigest()
    txt_path = os.path.join(output_dir, "lock.txt")
    with open(txt_path, "wb") as f:
        f.write(txt_bytes)

    # 3. Checksums
    chk_content = (
        f"{lock_digest}  lock.json\n"
        f"{txt_sha}  lock.txt\n"
    )
    chk_path = os.path.join(output_dir, "checksums.sha256")
    with open(chk_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(chk_content)

    return lock_payload, lock_digest


def run_lock_pipeline(
    proposal_dir: str,
    decision_dir: str,
    lock_dir: str,
    evaluation_time_utc: Optional[str] = None,
    decision_override: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], str, Dict[str, Any], str]:
    """
    Executes Phase 1, Phase 2, and Phase 3:
    1. Materializes human decision
    2. Validates decision against Proposal V2
    3. Computes real ALVORADA_LOCK_PAYLOAD and LOCK_DIGEST
    """
    # 1. Verify proposal directory checksums and load proposal
    verify_directory_checksums(proposal_dir, required=True)
    proposal_file = os.path.join(proposal_dir, "lock-proposal.json")
    with open(proposal_file, "r", encoding="utf-8") as f:
        proposal = json.load(f)

    validate_lock_proposal(proposal)

    # 2. Materialize human decision
    decision, decision_digest = materialize_human_decision(
        output_dir=decision_dir,
        decision_data=decision_override,
    )
    verify_directory_checksums(decision_dir, required=True)

    # 3. Validate decision against proposal with explicit evaluation time
    eval_time = evaluation_time_utc or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    is_valid, errors, report = verify_human_decision(decision, proposal, eval_time)
    if not is_valid:
        raise ValueError(f"HUMAN_DECISION_VALIDATION_FAILED: {errors}")

    if decision.get("selected_gpu") != "swiftshader":
        raise ValueError(f"UNEXPECTED_SELECTED_GPU: expected 'swiftshader', got {decision.get('selected_gpu')}")

    # 4. Compute lock payload and digest
    is_valid_lock, lock_digest, lock_payload, lock_errors = compute_lock_candidate(
        proposal=proposal,
        human_decision=decision,
        evaluation_time_utc=eval_time,
    )
    if not is_valid_lock or not lock_digest or not lock_payload:
        raise RuntimeError(f"LOCK_COMPUTATION_FAILED: {lock_errors}")

    # Invariants: 3 distinct digests
    cat_digest = proposal["catalog_digest"]
    prop_digest = compute_lock_proposal_digest(proposal)
    if cat_digest == prop_digest or prop_digest == lock_digest or cat_digest == lock_digest:
        raise RuntimeError("DIGEST_COLLISION: catalog, proposal, and lock digests must be pairwise distinct")

    # 5. Materialize lock payload artifacts
    materialize_lock_payload(
        output_dir=lock_dir,
        lock_payload=lock_payload,
        lock_digest=lock_digest,
    )
    verify_directory_checksums(lock_dir, required=True)

    return decision, decision_digest, lock_payload, lock_digest


def main() -> None:
    parser = argparse.ArgumentParser(description="ALVORADA Lock Runner")
    parser.add_argument(
        "--proposal-dir",
        default="experiments/reliability-harness/evidence/lock-proposal",
        help="Path to proposal artifacts directory",
    )
    parser.add_argument(
        "--decision-dir",
        default="experiments/reliability-harness/evidence/human-decision",
        help="Target directory for human decision artifacts",
    )
    parser.add_argument(
        "--lock-dir",
        default="experiments/reliability-harness/evidence/lock",
        help="Target directory for lock artifacts",
    )
    parser.add_argument(
        "--eval-time",
        default=None,
        help="Evaluation timestamp UTC (YYYY-MM-DDTHH:MM:SSZ)",
    )
    args = parser.parse_args()

    try:
        decision, dec_digest, lock_payload, lock_digest = run_lock_pipeline(
            proposal_dir=args.proposal_dir,
            decision_dir=args.decision_dir,
            lock_dir=args.lock_dir,
            evaluation_time_utc=args.eval_time,
        )
    except Exception as e:
        print(f"LOCK_PIPELINE_ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print("LOCK_PIPELINE_SUCCESS")
    print(f"DECISION_DIGEST={dec_digest}")
    print(f"LOCK_DIGEST={lock_digest}")
    print(f"SELECTED_GPU={lock_payload['selected_gpu']}")
    print(f"PROPOSAL_DIGEST={lock_payload['proposal_digest']}")
    print(f"CATALOG_DIGEST={lock_payload['catalog_digest']}")
    sys.exit(0)


if __name__ == "__main__":
    main()
