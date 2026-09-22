#!/usr/bin/env python3
"""
ALVORADA — Proposal Assembly Runner
Campaign: ALVORADA G1 EMPIRICAL ACCELERATION CAMPAIGN 001 (Phase 3 & 4)

Synthesizes empirical catalog projection and ephemeral GPU capability evidence
into an immutable, validated ALVORADA_LOCK_PROPOSAL_V1.
Computes LOCK_PROPOSAL_DIGEST and verifies all fail-closed contract invariants.

STOPPING BOUNDARY:
Stops strictly before human authority.
Does NOT select a GPU.
Does NOT approve the lock.
"""

import argparse
import hashlib
import json
import os
import sys
from typing import Any, Dict, Optional, Tuple

# Ensure local module imports work
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from catalog_core import (
    canonicalize_json_v1,
    hash_canonical_json_v1,
    validate_canonical_timestamp,
)
from catalog_lock_model import (
    CONTRACT_LOCK_PROPOSAL,
    PROPOSAL_STATE_PENDING,
    create_catalog_digest_payload,
    create_lock_proposal,
    validate_lock_proposal,
)


def load_canonical_json_file(file_path: str) -> Dict[str, Any]:
    """Loads and parses a JSON file from disk. Fails closed if missing or invalid."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"FILE_NOT_FOUND: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise TypeError(f"EXPECTED_JSON_OBJECT: {file_path} does not contain a JSON dictionary")
    return data


def generate_proposal_report_text(
    proposal: Dict[str, Any],
    proposal_digest: str,
    catalog_digest: str,
    projection_sha256: str,
    gpu_evidence_sha256: str,
) -> str:
    """Generates human-readable audit text report for the assembled lock proposal."""
    env = proposal["environment"]
    prov = proposal["provenance"]
    fresh = proposal["freshness"]
    gpu = proposal["gpu_evidence"]
    hard_locks = proposal["hard_locks"]

    lines = [
        "ALVORADA LOCK PROPOSAL AUDIT REPORT",
        "==================================",
        f"Contract: {proposal['contract']}",
        f"Proposal State: {proposal['proposal_state']}",
        f"Ready for Human Review: {'YES' if proposal['ready_for_human_review'] else 'NO'}",
        "",
        "CRYPTOGRAPHIC IDENTITIES & INTEGRITY DIGESTS",
        "-------------------------------------------",
        f"Catalog Digest (CATALOG_DIGEST):             {catalog_digest}",
        f"Bound Catalog Projection SHA-256:           {projection_sha256}",
        f"GPU Evidence SHA-256:                        {gpu_evidence_sha256}",
        f"Lock Proposal Digest (LOCK_PROPOSAL_DIGEST): {proposal_digest}",
        "",
        "PROVENANCE & TRACEABILITY",
        "-------------------------",
        f"Repository Commit SHA: {prov['repository_commit_sha']}",
        f"Catalog CI Run ID:     {prov['catalog_run_id']}",
        f"Runner Image Label:    {prov['runner_image_label']}",
        f"Runner Image Version:  {prov['runner_image_version']}",
        "",
        "RUNNER ENVIRONMENT SPECIFICATION",
        "--------------------------------",
        f"Operating System:       {env['runner_os']}",
        f"JDK Major Version:      {env['jdk_major']}",
        f"Cmdline-tools Revision: {env['cmdline_tools_revision']}",
        f"Emulator Revision:      {env['emulator_revision']}",
        "",
        "FRESHNESS SPECIFICATION",
        "-----------------------",
        f"Observed At UTC: {fresh['observed_at']}",
        f"Fresh Until UTC: {fresh['fresh_until']}",
        f"Max Age Days:    {fresh['max_age_days']}",
        "",
        "HARD LOCK PACKAGES (5)",
        "----------------------",
    ]

    for idx, pkg in enumerate(hard_locks, start=1):
        lines.append(f"{idx}. {pkg['package_path']} -> {pkg['revision']}")

    lines.extend([
        "",
        "EPHEMERAL GPU CAPABILITY EVIDENCE",
        "---------------------------------",
        f"Overall Status:        {gpu['status']}",
        f"Parser Status:         {gpu['parser_status']}",
        f"Evidence Ready:        {'YES' if gpu['evidence_ready'] else 'NO'}",
        f"Emulator Revision:     {gpu['emulator_revision']}",
        f"Candidate Mode Count:  {len(gpu['candidate_modes'])}",
        f"Candidate Modes:       {', '.join(gpu['candidate_modes'])}",
        "",
        "DECISION BOUNDARY NOTICE:",
        "-------------------------",
        "THIS ARTIFACT REPRESENTS A PENDING PROPOSAL FOR HUMAN REVIEW.",
        "NO GPU MODE HAS BEEN SELECTED.",
        "NO LOCK HAS BEEN APPROVED.",
        "HUMAN AUTHORITY IS REQUIRED TO SELECT A GPU CANDIDATE AND PRODUCE AN APPROVED LOCK.",
        "",
        "END OF LOCK PROPOSAL REPORT",
        "",
    ])

    return "\n".join(lines)


def assemble_lock_proposal(
    catalog_projection_path: str,
    gpu_evidence_path: str,
    output_dir: str,
    environment_override: Optional[Dict[str, Any]] = None,
    provenance_override: Optional[Dict[str, Any]] = None,
    freshness_override: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Dict[str, Any], str]:
    """
    Assembles, validates, and writes ALVORADA_LOCK_PROPOSAL_V1.
    Returns (exit_code, proposal_dict, proposal_digest).
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Load catalog projection and derive catalog digest payload
    projection = load_canonical_json_file(catalog_projection_path)
    proj_bytes = canonicalize_json_v1(projection)
    projection_sha256 = hashlib.sha256(proj_bytes).hexdigest()

    catalog_digest_payload = create_catalog_digest_payload(projection)
    catalog_digest = hash_canonical_json_v1(catalog_digest_payload)

    # 2. Load GPU evidence
    gpu_evidence = load_canonical_json_file(gpu_evidence_path)
    gpu_bytes = canonicalize_json_v1(gpu_evidence)
    gpu_evidence_sha256 = hashlib.sha256(gpu_bytes).hexdigest()

    # 3. Resolve environment, provenance, and freshness
    environment = environment_override or {
        "cmdline_tools_revision": "12.0",
        "emulator_revision": "37.1.11",
        "jdk_major": 17,
        "runner_image_label": "ubuntu24",
        "runner_image_version": "20260907.300.1",
        "runner_os": "Linux",
    }

    provenance = provenance_override or {
        "catalog_run_id": "35676154497",
        "repository_commit_sha": "8570a837852a2ab669092ac3940086a1fdc1cb81",
        "runner_image_label": "ubuntu24",
        "runner_image_version": "20260907.300.1",
    }

    freshness = freshness_override or {
        "observed_at": "2026-09-22T01:32:53Z",
        "fresh_until": "2026-09-29T01:32:53Z",
        "max_age_days": 7,
    }

    # 4. Construct and validate proposal under catalog_lock_model
    proposal = create_lock_proposal(
        catalog_digest_payload=catalog_digest_payload,
        environment=environment,
        gpu_evidence=gpu_evidence,
        freshness=freshness,
        provenance=provenance,
    )

    # 5. Compute LOCK_PROPOSAL_DIGEST
    proposal_bytes = canonicalize_json_v1(proposal)
    proposal_digest = hashlib.sha256(proposal_bytes).hexdigest()

    # 6. Verify adversarial invariants
    # 6.1 Three digests must be distinct
    if catalog_digest == proposal_digest:
        raise RuntimeError("CORRUPTION: CATALOG_DIGEST == LOCK_PROPOSAL_DIGEST")

    # 6.2 Binding to projection_sha256
    if gpu_evidence["projection_sha256"] != projection_sha256:
        raise RuntimeError(
            f"PROJECTION_MISMATCH: gpu_evidence.projection_sha256 ({gpu_evidence['projection_sha256']}) != computed ({projection_sha256})"
        )

    # 6.3 Tripartite emulator revision alignment
    hl_emu = next(p["revision"] for p in proposal["hard_locks"] if p["package_path"] == "emulator")
    if hl_emu != environment["emulator_revision"] or hl_emu != gpu_evidence["emulator_revision"]:
        raise RuntimeError("TRIPARTITE_ALIGNMENT_FAILURE: emulator revision mismatch")

    # 6.4 ready_for_human_review must be True
    if not proposal.get("ready_for_human_review"):
        raise RuntimeError("PROPOSAL_NOT_READY: ready_for_human_review is not True")

    # 7. Write proposal artifacts to output directory
    proposal_json_path = os.path.join(output_dir, "lock-proposal.json")
    with open(proposal_json_path, "wb") as f:
        f.write(proposal_bytes)

    proposal_txt_content = generate_proposal_report_text(
        proposal=proposal,
        proposal_digest=proposal_digest,
        catalog_digest=catalog_digest,
        projection_sha256=projection_sha256,
        gpu_evidence_sha256=gpu_evidence_sha256,
    )
    proposal_txt_bytes = proposal_txt_content.encode("utf-8")
    proposal_txt_path = os.path.join(output_dir, "lock-proposal.txt")
    with open(proposal_txt_path, "wb") as f:
        f.write(proposal_txt_bytes)

    proposal_txt_sha = hashlib.sha256(proposal_txt_bytes).hexdigest()

    checksums_content = (
        f"{proposal_digest}  lock-proposal.json\n"
        f"{proposal_txt_sha}  lock-proposal.txt\n"
    )
    checksums_path = os.path.join(output_dir, "checksums.sha256")
    with open(checksums_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(checksums_content)

    return 0, proposal, proposal_digest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ALVORADA Lock Proposal Assembly Runner"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="experiments/reliability-harness/artifacts/lock-proposal",
        help="Target output directory for proposal artifacts",
    )
    parser.add_argument(
        "--catalog-projection",
        default="experiments/reliability-harness/artifacts/catalog-discovery-8570a837852a2ab669092ac3940086a1fdc1cb81-35676154497/catalog-projection.json",
        help="Path to catalog-projection.json from Phase 1",
    )
    parser.add_argument(
        "--gpu-evidence",
        default="experiments/reliability-harness/evidence/gpu-evidence-35729959417/gpu-evidence.json",
        help="Path to gpu-evidence.json from Phase 2",
    )

    args = parser.parse_args()

    try:
        exit_code, proposal, proposal_digest = assemble_lock_proposal(
            catalog_projection_path=args.catalog_projection,
            gpu_evidence_path=args.gpu_evidence,
            output_dir=args.output_dir,
        )
    except Exception as e:
        print(f"PROPOSAL_ASSEMBLY_ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"PROPOSAL_STATE={proposal['proposal_state']}")
    print(f"READY_FOR_HUMAN_REVIEW={'YES' if proposal['ready_for_human_review'] else 'NO'}")
    print(f"CATALOG_DIGEST={proposal['catalog_digest']}")
    print(f"LOCK_PROPOSAL_DIGEST={proposal_digest}")
    print(f"CANDIDATE_GPU_MODES={','.join(proposal['gpu_evidence']['candidate_modes'])}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
