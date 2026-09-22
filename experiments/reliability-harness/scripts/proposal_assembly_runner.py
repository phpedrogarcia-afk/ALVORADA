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
    CONTRACT_LOCK_PROPOSAL_V2,
    PROPOSAL_STATE_PENDING,
    create_catalog_digest_payload,
    create_lock_proposal,
    create_lock_proposal_v2,
    build_lock_proposal_v2_from_provenance,
    validate_lock_proposal,
    compute_lock_proposal_digest,
    create_gpu_projection,
    compute_gpu_projection_sha256,
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


def verify_directory_checksums(directory: str, required: bool = True) -> None:
    """Verifies that all files listed in checksums.sha256 match their cryptographic hashes."""
    chk_file = os.path.join(directory, "checksums.sha256")
    if not os.path.isfile(chk_file):
        if required:
            raise FileNotFoundError(f"MISSING_CHECKSUMS_FILE: checksums.sha256 missing in {directory}")
        return
    with open(chk_file, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        expected_sha, fname = parts[0], parts[1].strip()
        fpath = os.path.join(directory, fname)
        if not os.path.isfile(fpath):
            raise FileNotFoundError(
                f"CHECKSUM_FILE_MISSING: {fname} listed in checksums.sha256 was not found in {directory}"
            )
        with open(fpath, "rb") as bf:
            actual_sha = hashlib.sha256(bf.read()).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(
                f"CHECKSUM_MISMATCH: {fname} in {directory} has sha256 {actual_sha}, expected {expected_sha}"
            )


def generate_proposal_report_text(
    proposal: Dict[str, Any],
    proposal_digest: str,
    catalog_digest: str,
    catalog_projection_sha256: str,
    gpu_projection_sha256: str,
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
        f"Bound Catalog Projection SHA-256:           {catalog_projection_sha256}",
        f"Bound GPU Projection SHA-256:               {gpu_projection_sha256}",
        f"GPU Evidence SHA-256:                        {gpu_evidence_sha256}",
        f"Lock Proposal Digest (LOCK_PROPOSAL_DIGEST): {proposal_digest}",
        "",
        "PROVENANCE & TRACEABILITY",
        "-------------------------",
    ]

    if proposal["contract"] == CONTRACT_LOCK_PROPOSAL_V2:
        lines.extend([
            f"Catalog Commit SHA:    {prov['catalog_commit_sha']}",
            f"Catalog CI Run ID:     {prov['catalog_run_id']}",
            f"GPU Commit SHA:        {prov['gpu_commit_sha']}",
            f"GPU CI Run ID:         {prov['gpu_run_id']}",
            f"Runner Image Label:    {prov['runner_image_label']}",
            f"Runner Image Version:  {prov['runner_image_version']}",
        ])
    else:
        lines.extend([
            f"Repository Commit SHA: {prov['repository_commit_sha']}",
            f"Catalog CI Run ID:     {prov['catalog_run_id']}",
            f"Runner Image Label:    {prov['runner_image_label']}",
            f"Runner Image Version:  {prov['runner_image_version']}",
        ])

    lines.extend([
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
    ])

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
    output_dir: str,
    catalog_dir: Optional[str] = None,
    gpu_dir: Optional[str] = None,
    catalog_projection_path: Optional[str] = None,
    gpu_evidence_path: Optional[str] = None,
    environment_override: Optional[Dict[str, Any]] = None,
    provenance_override: Optional[Dict[str, Any]] = None,
    freshness_override: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Dict[str, Any], str]:
    """
    Assembles, validates, and writes ALVORADA_LOCK_PROPOSAL (V2 when provenance available, V1 fallback).
    Returns (exit_code, proposal_dict, proposal_digest).
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Resolve artifact directories and files
    cat_dir = catalog_dir or (os.path.dirname(os.path.abspath(catalog_projection_path)) if catalog_projection_path else None)
    g_dir = gpu_dir or (os.path.dirname(os.path.abspath(gpu_evidence_path)) if gpu_evidence_path else None)

    if not cat_dir and not catalog_projection_path:
        raise ValueError("MISSING_INPUT: Neither catalog_dir nor catalog_projection_path was provided")
    if not g_dir and not gpu_evidence_path:
        raise ValueError("MISSING_INPUT: Neither gpu_dir nor gpu_evidence_path was provided")

    cat_proj_file = catalog_projection_path or os.path.join(cat_dir, "catalog-projection.json")
    gpu_ev_file = gpu_evidence_path or os.path.join(g_dir, "gpu-evidence.json")

    # 2. Verify artifact checksums (strictly required when directories are provided)
    if catalog_dir and os.path.isdir(catalog_dir):
        verify_directory_checksums(catalog_dir, required=True)
    elif cat_dir and os.path.isdir(cat_dir):
        verify_directory_checksums(cat_dir, required=False)

    if gpu_dir and os.path.isdir(gpu_dir):
        verify_directory_checksums(gpu_dir, required=True)
    elif g_dir and os.path.isdir(g_dir):
        verify_directory_checksums(g_dir, required=False)

    # 3. Load primary artifacts
    projection = load_canonical_json_file(cat_proj_file)
    proj_bytes = canonicalize_json_v1(projection)
    catalog_projection_sha256 = hashlib.sha256(proj_bytes).hexdigest()

    catalog_digest_payload = create_catalog_digest_payload(projection)
    catalog_digest = hash_canonical_json_v1(catalog_digest_payload)

    gpu_evidence = load_canonical_json_file(gpu_ev_file)
    gpu_bytes = canonicalize_json_v1(gpu_evidence)
    gpu_evidence_sha256 = hashlib.sha256(gpu_bytes).hexdigest()

    # 4. Check for V2 provenance artifacts
    cat_prov_file = os.path.join(cat_dir, "catalog-provenance.json") if cat_dir else None
    gpu_proj_file = os.path.join(g_dir, "gpu-projection.json") if g_dir else None
    gpu_prov_file = os.path.join(g_dir, "gpu-provenance.json") if g_dir else None

    is_v2 = (
        cat_prov_file
        and os.path.isfile(cat_prov_file)
        and gpu_proj_file
        and os.path.isfile(gpu_proj_file)
        and gpu_prov_file
        and os.path.isfile(gpu_prov_file)
        and not (environment_override or provenance_override or freshness_override)
    )

    if is_v2:
        catalog_provenance = load_canonical_json_file(cat_prov_file)
        gpu_projection = load_canonical_json_file(gpu_proj_file)
        gpu_provenance = load_canonical_json_file(gpu_prov_file)

        gpu_projection_sha256 = hashlib.sha256(canonicalize_json_v1(gpu_projection)).hexdigest()

        proposal = build_lock_proposal_v2_from_provenance(
            catalog_digest_payload=catalog_digest_payload,
            catalog_provenance=catalog_provenance,
            gpu_evidence=gpu_evidence,
            gpu_provenance=gpu_provenance,
            gpu_projection=gpu_projection,
        )
    else:
        # V1 / explicit override pathway (used by mutation and unit tests)
        if len(gpu_evidence.get("candidate_modes", [])) >= 1 and gpu_evidence.get("emulator_revision"):
            gpu_proj = create_gpu_projection(
                gpu_evidence["emulator_revision"],
                gpu_evidence["candidate_modes"]
            )
            gpu_projection_sha256 = compute_gpu_projection_sha256(gpu_proj)
        else:
            gpu_projection_sha256 = gpu_evidence.get("projection_sha256", "0" * 64)

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

        # If provenance has V2 keys, create V2; else V1
        if "catalog_commit_sha" in provenance:
            proposal = create_lock_proposal_v2(
                catalog_digest_payload=catalog_digest_payload,
                environment=environment,
                gpu_evidence=gpu_evidence,
                freshness=freshness,
                provenance=provenance,
            )
        else:
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
    if gpu_evidence["projection_sha256"] != gpu_projection_sha256:
        raise RuntimeError(
            f"PROJECTION_MISMATCH: gpu_evidence.projection_sha256 ({gpu_evidence['projection_sha256']}) != computed ({gpu_projection_sha256})"
        )

    # 6.3 Tripartite emulator revision alignment
    hl_emu = next(p["revision"] for p in proposal["hard_locks"] if p["package_path"] == "emulator")
    if hl_emu != proposal["environment"]["emulator_revision"] or hl_emu != gpu_evidence["emulator_revision"]:
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
        catalog_projection_sha256=catalog_projection_sha256,
        gpu_projection_sha256=gpu_projection_sha256,
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
        "--catalog-dir",
        default=None,
        help="Path to catalog discovery artifacts directory",
    )
    parser.add_argument(
        "--gpu-dir",
        default=None,
        help="Path to GPU capability evidence artifacts directory",
    )
    parser.add_argument(
        "--catalog-projection",
        default=None,
        help="Path to catalog-projection.json (optional override)",
    )
    parser.add_argument(
        "--gpu-evidence",
        default=None,
        help="Path to gpu-evidence.json (optional override)",
    )

    args = parser.parse_args()

    if not args.catalog_dir and not args.catalog_projection:
        print("ERROR: Must provide --catalog-dir or --catalog-projection", file=sys.stderr)
        sys.exit(1)
    if not args.gpu_dir and not args.gpu_evidence:
        print("ERROR: Must provide --gpu-dir or --gpu-evidence", file=sys.stderr)
        sys.exit(1)

    try:
        exit_code, proposal, proposal_digest = assemble_lock_proposal(
            output_dir=args.output_dir,
            catalog_dir=args.catalog_dir,
            gpu_dir=args.gpu_dir,
            catalog_projection_path=args.catalog_projection,
            gpu_evidence_path=args.gpu_evidence,
        )
    except Exception as e:
        print(f"PROPOSAL_ASSEMBLY_ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"PROPOSAL_CONTRACT={proposal['contract']}")
    print(f"PROPOSAL_STATE={proposal['proposal_state']}")
    print(f"READY_FOR_HUMAN_REVIEW={'YES' if proposal['ready_for_human_review'] else 'NO'}")
    print(f"CATALOG_DIGEST={proposal['catalog_digest']}")
    print(f"LOCK_PROPOSAL_DIGEST={proposal_digest}")
    print(f"CANDIDATE_GPU_MODES={','.join(proposal['gpu_evidence']['candidate_modes'])}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
