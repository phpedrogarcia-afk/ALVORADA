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
from catalog_lock_model import (
    CONTRACT_LOCK_PROPOSAL,
    CONTRACT_LOCK_PROPOSAL_V2,
    create_gpu_projection,
    compute_gpu_projection_sha256,
    create_catalog_provenance,
    create_gpu_provenance,
    create_catalog_digest_payload,
)
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

        modes = ["auto", "host", "lavapipe", "software", "swangle", "swiftshader"]
        gpu_proj = create_gpu_projection("37.1.11", modes)
        gpu_proj_sha = compute_gpu_projection_sha256(gpu_proj)

        self.gpu_evidence_path = os.path.join(self.temp_dir, "gpu-evidence.json")
        self.gpu_evidence_data = {
            "candidate_modes": modes,
            "emulator_revision": "37.1.11",
            "evidence_ready": True,
            "parser_status": "PASS_STRICT",
            "projection_sha256": gpu_proj_sha,
            "status": "PASS_STRICT",
        }
        with open(self.gpu_evidence_path, "wb") as f:
            f.write(canonicalize_json_v1(self.gpu_evidence_data))

        # Explicit test fixtures (FG-002: no hardcoded defaults in production)
        self.explicit_env = {
            "cmdline_tools_revision": "12.0",
            "emulator_revision": "37.1.11",
            "jdk_major": 17,
            "runner_image_label": "ubuntu24",
            "runner_image_version": "20260907.300.1",
            "runner_os": "Linux",
        }
        self.explicit_prov = {
            "catalog_run_id": "35676154497",
            "repository_commit_sha": "8570a837852a2ab669092ac3940086a1fdc1cb81",
            "runner_image_label": "ubuntu24",
            "runner_image_version": "20260907.300.1",
        }
        self.explicit_fresh = {
            "observed_at": "2026-09-22T01:32:53Z",
            "fresh_until": "2026-09-29T01:32:53Z",
            "max_age_days": 7,
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_checksums(self, directory: str) -> None:
        entries = []
        for name in sorted(os.listdir(directory)):
            if name == "checksums.sha256":
                continue
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()
                entries.append(f"{digest}  {name}\n")
        with open(os.path.join(directory, "checksums.sha256"), "w", encoding="utf-8") as f:
            f.writelines(entries)

    def test_assemble_lock_proposal_v1_with_all_explicit_values_passes(self):
        exit_code, proposal, proposal_digest = assemble_lock_proposal(
            catalog_projection_path=self.projection_path,
            gpu_evidence_path=self.gpu_evidence_path,
            output_dir=self.out_dir,
            environment_override=self.explicit_env,
            provenance_override=self.explicit_prov,
            freshness_override=self.explicit_fresh,
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

    def test_assemble_v1_without_explicit_environment_fails(self):
        with self.assertRaises(ValueError) as ctx:
            assemble_lock_proposal(
                catalog_projection_path=self.projection_path,
                gpu_evidence_path=self.gpu_evidence_path,
                output_dir=self.out_dir,
                provenance_override=self.explicit_prov,
                freshness_override=self.explicit_fresh,
            )
        self.assertIn("MISSING_EXPLICIT_INPUT: environment_override", str(ctx.exception))

    def test_assemble_v1_without_explicit_provenance_fails(self):
        with self.assertRaises(ValueError) as ctx:
            assemble_lock_proposal(
                catalog_projection_path=self.projection_path,
                gpu_evidence_path=self.gpu_evidence_path,
                output_dir=self.out_dir,
                environment_override=self.explicit_env,
                freshness_override=self.explicit_fresh,
            )
        self.assertIn("MISSING_EXPLICIT_INPUT: provenance_override", str(ctx.exception))

    def test_assemble_v1_without_explicit_freshness_fails(self):
        with self.assertRaises(ValueError) as ctx:
            assemble_lock_proposal(
                catalog_projection_path=self.projection_path,
                gpu_evidence_path=self.gpu_evidence_path,
                output_dir=self.out_dir,
                environment_override=self.explicit_env,
                provenance_override=self.explicit_prov,
            )
        self.assertIn("MISSING_EXPLICIT_INPUT: freshness_override", str(ctx.exception))

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
                environment_override=self.explicit_env,
                provenance_override=self.explicit_prov,
                freshness_override=self.explicit_fresh,
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
                provenance_override=self.explicit_prov,
                freshness_override=self.explicit_fresh,
            )

    def test_assemble_v2_from_directories_success(self):
        cat_dir = os.path.join(self.temp_dir, "cat_artifacts")
        gpu_dir = os.path.join(self.temp_dir, "gpu_artifacts")
        os.makedirs(cat_dir, exist_ok=True)
        os.makedirs(gpu_dir, exist_ok=True)

        # 1. Catalog artifacts
        shutil.copyfile(self.projection_path, os.path.join(cat_dir, "catalog-projection.json"))
        cat_payload = create_catalog_digest_payload(self.projection_data)
        cat_digest = hashlib.sha256(canonicalize_json_v1(cat_payload)).hexdigest()
        cat_proj_sha = hashlib.sha256(canonicalize_json_v1(self.projection_data)).hexdigest()

        cat_prov = create_catalog_provenance(
            repository_commit_sha="1111111111111111111111111111111111111111",
            run_id="101",
            observed_at="2026-09-22T02:00:00Z",
            runner_os="Linux",
            runner_image_label="ubuntu24",
            runner_image_version="20260907.300.1",
            jdk_major=17,
            cmdline_tools_revision="12.0",
            catalog_projection_sha256=cat_proj_sha,
            catalog_digest=cat_digest,
        )
        cat_prov_bytes = canonicalize_json_v1(cat_prov)
        with open(os.path.join(cat_dir, "catalog-provenance.json"), "wb") as f:
            f.write(cat_prov_bytes)
        cat_prov_sha = hashlib.sha256(cat_prov_bytes).hexdigest()

        with open(os.path.join(cat_dir, "checksums.sha256"), "w", encoding="utf-8") as f:
            f.write(f"{cat_proj_sha}  catalog-projection.json\n{cat_prov_sha}  catalog-provenance.json\n")

        # 2. GPU artifacts
        modes = ["auto", "host", "lavapipe", "software", "swangle", "swiftshader"]
        gpu_proj = create_gpu_projection("37.1.11", modes)
        gpu_proj_bytes = canonicalize_json_v1(gpu_proj)
        gpu_proj_sha = hashlib.sha256(gpu_proj_bytes).hexdigest()
        with open(os.path.join(gpu_dir, "gpu-projection.json"), "wb") as f:
            f.write(gpu_proj_bytes)

        gpu_prov = create_gpu_provenance(
            repository_commit_sha="2222222222222222222222222222222222222222",
            run_id="202",
            observed_at="2026-09-22T04:00:00Z",
            runner_os="Linux",
            runner_image_label="ubuntu24",
            runner_image_version="20260907.300.1",
            emulator_revision="37.1.11",
            gpu_projection_sha256=gpu_proj_sha,
        )
        gpu_prov_bytes = canonicalize_json_v1(gpu_prov)
        gpu_prov_sha = hashlib.sha256(gpu_prov_bytes).hexdigest()
        with open(os.path.join(gpu_dir, "gpu-provenance.json"), "wb") as f:
            f.write(gpu_prov_bytes)

        gpu_ev = dict(self.gpu_evidence_data)
        gpu_ev["projection_sha256"] = gpu_proj_sha
        gpu_ev_bytes = canonicalize_json_v1(gpu_ev)
        gpu_ev_sha = hashlib.sha256(gpu_ev_bytes).hexdigest()
        with open(os.path.join(gpu_dir, "gpu-evidence.json"), "wb") as f:
            f.write(gpu_ev_bytes)

        with open(os.path.join(gpu_dir, "checksums.sha256"), "w", encoding="utf-8") as f:
            f.write(f"{gpu_proj_sha}  gpu-projection.json\n{gpu_prov_sha}  gpu-provenance.json\n{gpu_ev_sha}  gpu-evidence.json\n")

        # Execute assembly
        exit_code, proposal, prop_digest = assemble_lock_proposal(
            output_dir=self.out_dir,
            catalog_dir=cat_dir,
            gpu_dir=gpu_dir,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(proposal["contract"], "ALVORADA_LOCK_PROPOSAL_V2")
        self.assertEqual(proposal["provenance"]["catalog_commit_sha"], "1111111111111111111111111111111111111111")
        self.assertEqual(proposal["provenance"]["catalog_run_id"], "101")
        self.assertEqual(proposal["provenance"]["gpu_commit_sha"], "2222222222222222222222222222222222222222")
        self.assertEqual(proposal["provenance"]["gpu_run_id"], "202")

        # Causal freshness: proposal observed_at = max(cat_obs, gpu_obs)
        self.assertEqual(proposal["freshness"]["observed_at"], "2026-09-22T04:00:00Z")
        self.assertEqual(proposal["freshness"]["fresh_until"], "2026-09-29T04:00:00Z")

    def test_assemble_v2_tampered_checksum_fails(self):
        cat_dir = os.path.join(self.temp_dir, "cat_tampered")
        gpu_dir = os.path.join(self.temp_dir, "gpu_ok")
        os.makedirs(cat_dir, exist_ok=True)
        os.makedirs(gpu_dir, exist_ok=True)

        with open(os.path.join(cat_dir, "catalog-projection.json"), "wb") as f:
            f.write(b"tampered")
        with open(os.path.join(cat_dir, "checksums.sha256"), "w", encoding="utf-8") as f:
            f.write("0000000000000000000000000000000000000000000000000000000000000000  catalog-projection.json\n")

        with self.assertRaises(ValueError) as ctx:
            assemble_lock_proposal(
                output_dir=self.out_dir,
                catalog_dir=cat_dir,
                gpu_dir=gpu_dir,
            )
        self.assertIn("CHECKSUM_MISMATCH", str(ctx.exception))

    def test_assemble_v2_cross_run_runner_mismatch_fails(self):
        cat_dir = os.path.join(self.temp_dir, "cat_runner")
        gpu_dir = os.path.join(self.temp_dir, "gpu_runner")
        os.makedirs(cat_dir, exist_ok=True)
        os.makedirs(gpu_dir, exist_ok=True)

        shutil.copyfile(self.projection_path, os.path.join(cat_dir, "catalog-projection.json"))
        cat_payload = create_catalog_digest_payload(self.projection_data)
        cat_digest = hashlib.sha256(canonicalize_json_v1(cat_payload)).hexdigest()
        cat_proj_sha = hashlib.sha256(canonicalize_json_v1(self.projection_data)).hexdigest()

        cat_prov = create_catalog_provenance(
            repository_commit_sha="1111111111111111111111111111111111111111",
            run_id="101",
            observed_at="2026-09-22T02:00:00Z",
            runner_os="Linux",
            runner_image_label="ubuntu24",
            runner_image_version="20260907.300.1",
            jdk_major=17,
            cmdline_tools_revision="12.0",
            catalog_projection_sha256=cat_proj_sha,
            catalog_digest=cat_digest,
        )
        with open(os.path.join(cat_dir, "catalog-provenance.json"), "wb") as f:
            f.write(canonicalize_json_v1(cat_prov))

        modes = ["auto", "host", "lavapipe", "software", "swangle", "swiftshader"]
        gpu_proj = create_gpu_projection("37.1.11", modes)
        with open(os.path.join(gpu_dir, "gpu-projection.json"), "wb") as f:
            f.write(canonicalize_json_v1(gpu_proj))

        # Runner image label mismatch on GPU run
        gpu_prov = create_gpu_provenance(
            repository_commit_sha="2222222222222222222222222222222222222222",
            run_id="202",
            observed_at="2026-09-22T04:00:00Z",
            runner_os="Linux",
            runner_image_label="ubuntu22",  # Mismatch!
            runner_image_version="20260907.300.1",
            emulator_revision="37.1.11",
            gpu_projection_sha256=compute_gpu_projection_sha256(gpu_proj),
        )
        with open(os.path.join(gpu_dir, "gpu-provenance.json"), "wb") as f:
            f.write(canonicalize_json_v1(gpu_prov))

        gpu_ev = dict(self.gpu_evidence_data)
        gpu_ev["projection_sha256"] = compute_gpu_projection_sha256(gpu_proj)
        with open(os.path.join(gpu_dir, "gpu-evidence.json"), "wb") as f:
            f.write(canonicalize_json_v1(gpu_ev))

        self._write_checksums(cat_dir)
        self._write_checksums(gpu_dir)

        with self.assertRaises(ValueError) as ctx:
            assemble_lock_proposal(
                output_dir=self.out_dir,
                catalog_dir=cat_dir,
                gpu_dir=gpu_dir,
            )
        self.assertIn("CROSS_RUN_RUNNER_LABEL_MISMATCH", str(ctx.exception))

    def test_assemble_v2_cross_run_runner_version_mismatch_fails(self):
        cat_dir = os.path.join(self.temp_dir, "cat_version")
        gpu_dir = os.path.join(self.temp_dir, "gpu_version")
        os.makedirs(cat_dir, exist_ok=True)
        os.makedirs(gpu_dir, exist_ok=True)

        shutil.copyfile(self.projection_path, os.path.join(cat_dir, "catalog-projection.json"))
        cat_payload = create_catalog_digest_payload(self.projection_data)
        cat_digest = hashlib.sha256(canonicalize_json_v1(cat_payload)).hexdigest()
        cat_proj_sha = hashlib.sha256(canonicalize_json_v1(self.projection_data)).hexdigest()

        cat_prov = create_catalog_provenance(
            repository_commit_sha="1111111111111111111111111111111111111111",
            run_id="101",
            observed_at="2026-09-22T02:00:00Z",
            runner_os="Linux",
            runner_image_label="ubuntu24",
            runner_image_version="20260907.300.1",
            jdk_major=17,
            cmdline_tools_revision="12.0",
            catalog_projection_sha256=cat_proj_sha,
            catalog_digest=cat_digest,
        )
        with open(os.path.join(cat_dir, "catalog-provenance.json"), "wb") as f:
            f.write(canonicalize_json_v1(cat_prov))

        modes = ["auto", "host", "lavapipe", "software", "swangle", "swiftshader"]
        gpu_proj = create_gpu_projection("37.1.11", modes)
        with open(os.path.join(gpu_dir, "gpu-projection.json"), "wb") as f:
            f.write(canonicalize_json_v1(gpu_proj))

        # Runner image version mismatch on GPU run
        gpu_prov = create_gpu_provenance(
            repository_commit_sha="2222222222222222222222222222222222222222",
            run_id="202",
            observed_at="2026-09-22T04:00:00Z",
            runner_os="Linux",
            runner_image_label="ubuntu24",
            runner_image_version="20260901.100.0",  # Mismatch!
            emulator_revision="37.1.11",
            gpu_projection_sha256=compute_gpu_projection_sha256(gpu_proj),
        )
        with open(os.path.join(gpu_dir, "gpu-provenance.json"), "wb") as f:
            f.write(canonicalize_json_v1(gpu_prov))

        gpu_ev = dict(self.gpu_evidence_data)
        gpu_ev["projection_sha256"] = compute_gpu_projection_sha256(gpu_proj)
        with open(os.path.join(gpu_dir, "gpu-evidence.json"), "wb") as f:
            f.write(canonicalize_json_v1(gpu_ev))

        self._write_checksums(cat_dir)
        self._write_checksums(gpu_dir)

        with self.assertRaises(ValueError) as ctx:
            assemble_lock_proposal(
                output_dir=self.out_dir,
                catalog_dir=cat_dir,
                gpu_dir=gpu_dir,
            )
        self.assertIn("CROSS_RUN_RUNNER_VERSION_MISMATCH", str(ctx.exception))

    def test_assemble_v2_emulator_revision_mismatch_fails(self):
        cat_dir = os.path.join(self.temp_dir, "cat_emu")
        gpu_dir = os.path.join(self.temp_dir, "gpu_emu")
        os.makedirs(cat_dir, exist_ok=True)
        os.makedirs(gpu_dir, exist_ok=True)

        shutil.copyfile(self.projection_path, os.path.join(cat_dir, "catalog-projection.json"))
        cat_payload = create_catalog_digest_payload(self.projection_data)
        cat_digest = hashlib.sha256(canonicalize_json_v1(cat_payload)).hexdigest()
        cat_proj_sha = hashlib.sha256(canonicalize_json_v1(self.projection_data)).hexdigest()

        cat_prov = create_catalog_provenance(
            repository_commit_sha="1111111111111111111111111111111111111111",
            run_id="101",
            observed_at="2026-09-22T02:00:00Z",
            runner_os="Linux",
            runner_image_label="ubuntu24",
            runner_image_version="20260907.300.1",
            jdk_major=17,
            cmdline_tools_revision="12.0",
            catalog_projection_sha256=cat_proj_sha,
            catalog_digest=cat_digest,
        )
        with open(os.path.join(cat_dir, "catalog-provenance.json"), "wb") as f:
            f.write(canonicalize_json_v1(cat_prov))

        modes = ["auto", "host", "lavapipe", "software", "swangle", "swiftshader"]
        gpu_proj = create_gpu_projection("37.1.12", modes)  # Spliced 37.1.12 vs catalog 37.1.11!
        with open(os.path.join(gpu_dir, "gpu-projection.json"), "wb") as f:
            f.write(canonicalize_json_v1(gpu_proj))

        gpu_prov = create_gpu_provenance(
            repository_commit_sha="2222222222222222222222222222222222222222",
            run_id="202",
            observed_at="2026-09-22T04:00:00Z",
            runner_os="Linux",
            runner_image_label="ubuntu24",
            runner_image_version="20260907.300.1",
            emulator_revision="37.1.12",
            gpu_projection_sha256=compute_gpu_projection_sha256(gpu_proj),
        )
        with open(os.path.join(gpu_dir, "gpu-provenance.json"), "wb") as f:
            f.write(canonicalize_json_v1(gpu_prov))

        gpu_ev = dict(self.gpu_evidence_data)
        gpu_ev["emulator_revision"] = "37.1.12"
        gpu_ev["projection_sha256"] = compute_gpu_projection_sha256(gpu_proj)
        with open(os.path.join(gpu_dir, "gpu-evidence.json"), "wb") as f:
            f.write(canonicalize_json_v1(gpu_ev))

        self._write_checksums(cat_dir)
        self._write_checksums(gpu_dir)

        with self.assertRaises(ValueError) as ctx:
            assemble_lock_proposal(
                output_dir=self.out_dir,
                catalog_dir=cat_dir,
                gpu_dir=gpu_dir,
            )
        self.assertIn("EMULATOR_REVISION_MISMATCH", str(ctx.exception))

    def test_assemble_v2_tampered_gpu_evidence_checksum_fails(self):
        cat_dir = os.path.join(self.temp_dir, "cat_ok")
        gpu_dir = os.path.join(self.temp_dir, "gpu_tampered")
        os.makedirs(cat_dir, exist_ok=True)
        os.makedirs(gpu_dir, exist_ok=True)

        shutil.copyfile(self.projection_path, os.path.join(cat_dir, "catalog-projection.json"))
        self._write_checksums(cat_dir)

        with open(os.path.join(gpu_dir, "gpu-evidence.json"), "wb") as f:
            f.write(b"tampered_gpu_data")
        with open(os.path.join(gpu_dir, "checksums.sha256"), "w", encoding="utf-8") as f:
            f.write("0000000000000000000000000000000000000000000000000000000000000000  gpu-evidence.json\n")

        with self.assertRaises(ValueError) as ctx:
            assemble_lock_proposal(
                output_dir=self.out_dir,
                catalog_dir=cat_dir,
                gpu_dir=gpu_dir,
            )
        self.assertIn("CHECKSUM_MISMATCH", str(ctx.exception))

    def test_assemble_v2_missing_checksums_fails(self):
        cat_dir = os.path.join(self.temp_dir, "cat_no_chk")
        gpu_dir = os.path.join(self.temp_dir, "gpu_no_chk")
        os.makedirs(cat_dir, exist_ok=True)
        os.makedirs(gpu_dir, exist_ok=True)

        shutil.copyfile(self.projection_path, os.path.join(cat_dir, "catalog-projection.json"))
        shutil.copyfile(self.gpu_evidence_path, os.path.join(gpu_dir, "gpu-evidence.json"))

        with self.assertRaises(FileNotFoundError) as ctx:
            assemble_lock_proposal(
                output_dir=self.out_dir,
                catalog_dir=cat_dir,
                gpu_dir=gpu_dir,
            )
        self.assertIn("MISSING_CHECKSUMS_FILE", str(ctx.exception))

    def test_current_v2_proposal_digest_immutability(self):
        cat_evidence_dir = os.path.join(os.path.dirname(SCRIPTS_DIR), "evidence", "catalog-discovery-35734672486")
        gpu_evidence_dir = os.path.join(os.path.dirname(SCRIPTS_DIR), "evidence", "gpu-evidence-35734871241")
        if os.path.isdir(cat_evidence_dir) and os.path.isdir(gpu_evidence_dir):
            test_out = os.path.join(self.temp_dir, "immutability_test")
            exit_code, proposal, prop_digest = assemble_lock_proposal(
                output_dir=test_out,
                catalog_dir=cat_evidence_dir,
                gpu_dir=gpu_evidence_dir,
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                prop_digest,
                "5517290ec9b90cdcbc13ad34a1228a1ff422f2a5c2326d622e9f2ae249b411b4",
                "UNEXPECTED_EMPIRICAL_PROPOSAL_DRIFT",
            )


if __name__ == "__main__":
    unittest.main()
