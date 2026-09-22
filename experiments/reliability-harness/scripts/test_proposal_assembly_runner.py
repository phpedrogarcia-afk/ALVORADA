#!/usr/bin/env python3
"""
ALVORADA — Unit Test Suite for Proposal Assembly Runner
Campaign: ALVORADA G1 EMPIRICAL ACCELERATION CAMPAIGN 001 (Phase 3 & 4)
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from catalog_core import canonicalize_json_v1
from proposal_assembly_runner import (
    assemble_lock_proposal,
    generate_proposal_report_text,
    load_canonical_json_file,
)


class TestProposalAssemblyRunner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.out_dir = os.path.join(self.temp_dir, "artifacts")

        self.projection_path = os.path.join(self.temp_dir, "catalog-projection.json")
        self.projection_data = {
            "contract": "ALVORADA_CATALOG_PROJECTION_V1",
            "has_ambiguity": False,
            "is_complete": True,
            "packages": [
                {"catalog_revision": "36.0.0", "installed_revision": "36.0.0", "package_path": "build-tools;36.0.0", "state": "PRESENT_MATCHING_CATALOG"},
                {"catalog_revision": "37.1.11", "installed_revision": None, "package_path": "emulator", "state": "ABSENT"},
                {"catalog_revision": "37.0.1", "installed_revision": "37.0.1", "package_path": "platform-tools", "state": "PRESENT_MATCHING_CATALOG"},
                {"catalog_revision": "2", "installed_revision": "2", "package_path": "platforms;android-36", "state": "PRESENT_MATCHING_CATALOG"},
                {"catalog_revision": "2", "installed_revision": None, "package_path": "system-images;android-36;default;x86_64", "state": "ABSENT"},
            ],
        }
        with open(self.projection_path, "wb") as f:
            f.write(canonicalize_json_v1(self.projection_data))

        proj_sha = hashlib.sha256(canonicalize_json_v1(self.projection_data)).hexdigest()

        self.gpu_evidence_path = os.path.join(self.temp_dir, "gpu-evidence.json")
        self.gpu_evidence_data = {
            "candidate_modes": ["auto", "host", "lavapipe", "software", "swangle", "swiftshader"],
            "emulator_revision": "37.1.11",
            "evidence_ready": True,
            "parser_status": "PASS_STRICT",
            "projection_sha256": proj_sha,
            "status": "PASS_STRICT",
        }
        with open(self.gpu_evidence_path, "wb") as f:
            f.write(canonicalize_json_v1(self.gpu_evidence_data))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_assemble_lock_proposal_success(self):
        exit_code, proposal, proposal_digest = assemble_lock_proposal(
            catalog_projection_path=self.projection_path,
            gpu_evidence_path=self.gpu_evidence_path,
            output_dir=self.out_dir,
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(proposal["contract"], "ALVORADA_LOCK_PROPOSAL_V1")
        self.assertEqual(proposal["proposal_state"], "PENDING_HUMAN_REVIEW")
        self.assertTrue(proposal["ready_for_human_review"])
        self.assertEqual(len(proposal["hard_locks"]), 5)
        self.assertEqual(len(proposal["gpu_evidence"]["candidate_modes"]), 6)

        # Invariant: CATALOG_DIGEST != LOCK_PROPOSAL_DIGEST
        self.assertNotEqual(proposal["catalog_digest"], proposal_digest)

        # Artifacts on disk
        json_path = os.path.join(self.out_dir, "lock-proposal.json")
        txt_path = os.path.join(self.out_dir, "lock-proposal.txt")
        chk_path = os.path.join(self.out_dir, "checksums.sha256")

        self.assertTrue(os.path.isfile(json_path))
        self.assertTrue(os.path.isfile(txt_path))
        self.assertTrue(os.path.isfile(chk_path))

        with open(json_path, "rb") as f:
            bytes_on_disk = f.read()
        self.assertEqual(bytes_on_disk, canonicalize_json_v1(proposal))
        self.assertEqual(hashlib.sha256(bytes_on_disk).hexdigest(), proposal_digest)

        with open(chk_path, "r", encoding="utf-8") as f:
            chk_lines = f.readlines()
        self.assertEqual(len(chk_lines), 2)
        self.assertTrue(chk_lines[0].startswith(proposal_digest))

    def test_assemble_fails_on_projection_mismatch(self):
        # Alter projection_sha256 in gpu_evidence
        bad_gpu = dict(self.gpu_evidence_data)
        bad_gpu["projection_sha256"] = "0000000000000000000000000000000000000000000000000000000000000000"
        with open(self.gpu_evidence_path, "wb") as f:
            f.write(canonicalize_json_v1(bad_gpu))

        with self.assertRaises(RuntimeError) as ctx:
            assemble_lock_proposal(
                catalog_projection_path=self.projection_path,
                gpu_evidence_path=self.gpu_evidence_path,
                output_dir=self.out_dir,
            )
        self.assertIn("PROJECTION_MISMATCH", str(ctx.exception))

    def test_assemble_fails_on_tripartite_mismatch(self):
        # Change emulator revision in environment override
        bad_env = {
            "cmdline_tools_revision": "12.0",
            "emulator_revision": "35.0.0",
            "jdk_major": 17,
            "runner_image_label": "ubuntu24",
            "runner_image_version": "20260907.300.1",
            "runner_os": "Linux",
        }
        with self.assertRaises(ValueError):
            assemble_lock_proposal(
                catalog_projection_path=self.projection_path,
                gpu_evidence_path=self.gpu_evidence_path,
                output_dir=self.out_dir,
                environment_override=bad_env,
            )


if __name__ == "__main__":
    unittest.main()
