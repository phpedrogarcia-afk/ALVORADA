#!/usr/bin/env python3
"""
ALVORADA — Comprehensive Unit & Mutation Test Suite for Three-Digest Lock Model
Contract Version: RECOVERY-G1-002-R1

Validates:
1. CATALOG_DIGEST, LOCK_PROPOSAL_DIGEST, and LOCK_DIGEST three-way separation.
2. Pre-computed static SHA-256 fixtures verified with independent second-path byte builder.
3. Strict payload scoping and schema validation (no leakage of local paths, closed HumanDecision schema).
4. Dual-window freshness enforcement (reviewed_at and evaluation_time_utc, backdated decision cannot revive expired proposal).
5. Strict fail-closed GPU evidence (missing fields, regex-validated lowercase 64-hex projection hash, status checks, emulator revision binding).
6. Direct catalog payload bypass closure (validate_catalog_digest_payload called on external payloads).
7. Environment and provenance coherence (runner_image_label and runner_image_version).
8. ready_for_human_review boolean flag in proposal payload (ready_for_human_review != approval).
9. Mutation test matrix (proves sensitivity to changes and isolation of review_context from lock payload).
10. Human authority is external (HUMAN_AUTHORITY_EXTERNALLY_REQUIRED=True, LOCK_CANDIDATE_COMPUTED).
"""

import copy
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog_lock_model import (
    CONTRACT_CATALOG_DIGEST_PAYLOAD,
    CONTRACT_LOCK_PROPOSAL,
    CONTRACT_HUMAN_DECISION,
    CONTRACT_LOCK_PAYLOAD,
    PROPOSAL_STATE_PENDING,
    validate_catalog_digest_payload,
    create_catalog_digest_payload,
    compute_catalog_digest,
    validate_lock_proposal,
    create_lock_proposal,
    compute_lock_proposal_digest,
    verify_human_decision,
    compute_lock_candidate,
)


class TestThreeDigestModel(unittest.TestCase):
    """Validates three-digest separation, static fixtures, and independent second path."""

    FIXTURE_CATALOG_DIGEST = "6c27ebaa82b34492b4f99c8ef52e63fc76b7ac7da70b02208f42045b884e0677"
    FIXTURE_LOCK_PROPOSAL_DIGEST = "c4a2a86584ebe84e51073a521cebaf9f2c79ed2eafb387b065c19c786915cc1b"
    FIXTURE_LOCK_DIGEST = "c81ec5da2054ebdb626aad308f4c03c162144809b84338834649ce2b5a45ffe9"

    def setUp(self):
        self.sample_projection = {
            "contract": "ALVORADA_CATALOG_PROJECTION_V1",
            "has_ambiguity": False,
            "is_complete": True,
            "packages": [
                {"catalog_revision": "36.0.0", "installed_revision": "36.0.0", "package_path": "build-tools;36.0.0", "state": "PRESENT_MATCHING_CATALOG"},
                {"catalog_revision": "37.1.11", "installed_revision": "37.1.11", "package_path": "emulator", "state": "PRESENT_MATCHING_CATALOG"},
                {"catalog_revision": "36.0.0", "installed_revision": "36.0.0", "package_path": "platform-tools", "state": "PRESENT_MATCHING_CATALOG"},
                {"catalog_revision": "1", "installed_revision": "1", "package_path": "platforms;android-36", "state": "PRESENT_MATCHING_CATALOG"},
                {"catalog_revision": "2", "installed_revision": "2", "package_path": "system-images;android-36;default;x86_64", "state": "PRESENT_MATCHING_CATALOG"},
            ],
        }
        self.sample_env = {
            "cmdline_tools_revision": "19.0",
            "emulator_revision": "37.1.11",
            "jdk_major": 17,
            "runner_image_label": "ubuntu-24.04",
            "runner_image_version": "20240901.1",
            "runner_os": "Linux",
        }
        self.sample_gpu = {
            "candidate_modes": ["auto-no-window", "off", "swiftshader_indirect"],
            "emulator_revision": "37.1.11",
            "evidence_ready": True,
            "parser_status": "PASS_STRICT",
            "projection_sha256": "60c5a10abe62cbbba40f81967647a67f98b0357b5c6e41c422c331a2d8103467",
            "status": "PASS_STRICT",
        }
        self.sample_freshness = {
            "fresh_until": "2026-09-27T12:00:00Z",
            "max_age_days": 7,
            "observed_at": "2026-09-20T12:00:00Z",
        }
        self.sample_provenance = {
            "catalog_run_id": "35540374123",
            "repository_commit_sha": "43018b1f9b14cb9e580d2157e6cb623ee18de0d1",
            "runner_image_label": "ubuntu-24.04",
            "runner_image_version": "20240901.1",
        }
        self.sample_eval_time = "2026-09-21T15:30:00Z"

    def test_three_digests_computed_and_distinct(self):
        """Validates that CATALOG_DIGEST, LOCK_PROPOSAL_DIGEST, and LOCK_DIGEST are distinct and match fixtures."""
        cat_digest, cat_payload = compute_catalog_digest(self.sample_projection)
        self.assertEqual(cat_digest, self.FIXTURE_CATALOG_DIGEST)

        proposal = create_lock_proposal(
            cat_payload,
            self.sample_env,
            self.sample_gpu,
            self.sample_freshness,
            self.sample_provenance,
        )
        prop_digest = compute_lock_proposal_digest(proposal)
        self.assertEqual(prop_digest, self.FIXTURE_LOCK_PROPOSAL_DIGEST)
        self.assertTrue(proposal["ready_for_human_review"])
        self.assertEqual(proposal["proposal_state"], PROPOSAL_STATE_PENDING)

        decision = {
            "catalog_digest": cat_digest,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": prop_digest,
            "review_context": {"authority_basis": "EXTERNAL_FOUNDER_GATE"},
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }
        is_valid, lock_digest, lock_payload, errors = compute_lock_candidate(
            proposal, decision, self.sample_eval_time
        )
        self.assertTrue(is_valid, f"Failed to compute lock candidate: {errors}")
        self.assertEqual(lock_digest, self.FIXTURE_LOCK_DIGEST)

        # Invariant: all 3 must be mutually distinct
        self.assertNotEqual(cat_digest, prop_digest)
        self.assertNotEqual(prop_digest, lock_digest)
        self.assertNotEqual(cat_digest, lock_digest)

    def test_independent_second_path_verification(self):
        """Independent second-path verification constructing raw bytes manually without module functions."""
        # Raw byte builder for Catalog
        raw_cat = (
            b'{"channel":0,"contract":"ALVORADA_CATALOG_DIGEST_PAYLOAD_V1","packages":['
            b'{"catalog_revision":"36.0.0","package_path":"build-tools;36.0.0"},'
            b'{"catalog_revision":"37.1.11","package_path":"emulator"},'
            b'{"catalog_revision":"36.0.0","package_path":"platform-tools"},'
            b'{"catalog_revision":"1","package_path":"platforms;android-36"},'
            b'{"catalog_revision":"2","package_path":"system-images;android-36;default;x86_64"}'
            b']}'
        )
        self.assertEqual(hashlib.sha256(raw_cat).hexdigest(), self.FIXTURE_CATALOG_DIGEST)

        # Raw byte builder for Proposal
        raw_prop = (
            b'{"catalog_digest":"6c27ebaa82b34492b4f99c8ef52e63fc76b7ac7da70b02208f42045b884e0677",'
            b'"contract":"ALVORADA_LOCK_PROPOSAL_V1",'
            b'"environment":{"cmdline_tools_revision":"19.0","emulator_revision":"37.1.11","jdk_major":17,"runner_image_label":"ubuntu-24.04","runner_image_version":"20240901.1","runner_os":"Linux"},'
            b'"freshness":{"fresh_until":"2026-09-27T12:00:00Z","max_age_days":7,"observed_at":"2026-09-20T12:00:00Z"},'
            b'"gpu_evidence":{"candidate_modes":["auto-no-window","off","swiftshader_indirect"],"emulator_revision":"37.1.11","evidence_ready":true,"parser_status":"PASS_STRICT","projection_sha256":"60c5a10abe62cbbba40f81967647a67f98b0357b5c6e41c422c331a2d8103467","status":"PASS_STRICT"},'
            b'"hard_locks":['
            b'{"package_path":"build-tools;36.0.0","revision":"36.0.0"},'
            b'{"package_path":"emulator","revision":"37.1.11"},'
            b'{"package_path":"platform-tools","revision":"36.0.0"},'
            b'{"package_path":"platforms;android-36","revision":"1"},'
            b'{"package_path":"system-images;android-36;default;x86_64","revision":"2"}'
            b'],'
            b'"proposal_state":"PENDING_HUMAN_REVIEW",'
            b'"provenance":{"catalog_run_id":"35540374123","repository_commit_sha":"43018b1f9b14cb9e580d2157e6cb623ee18de0d1","runner_image_label":"ubuntu-24.04","runner_image_version":"20240901.1"},'
            b'"ready_for_human_review":true'
            b'}'
        )
        self.assertEqual(hashlib.sha256(raw_prop).hexdigest(), self.FIXTURE_LOCK_PROPOSAL_DIGEST)

        # Raw byte builder for Lock
        raw_lock = (
            b'{"catalog_digest":"6c27ebaa82b34492b4f99c8ef52e63fc76b7ac7da70b02208f42045b884e0677",'
            b'"contract":"ALVORADA_LOCK_PAYLOAD_V1",'
            b'"environment_locks":{"emulator_revision":"37.1.11","jdk_major":17},'
            b'"hard_locks":['
            b'{"package_path":"build-tools;36.0.0","revision":"36.0.0"},'
            b'{"package_path":"emulator","revision":"37.1.11"},'
            b'{"package_path":"platform-tools","revision":"36.0.0"},'
            b'{"package_path":"platforms;android-36","revision":"1"},'
            b'{"package_path":"system-images;android-36;default;x86_64","revision":"2"}'
            b'],'
            b'"proposal_digest":"' + self.FIXTURE_LOCK_PROPOSAL_DIGEST.encode('ascii') + b'",'
            b'"selected_gpu":"swiftshader_indirect"}'
        )
        self.assertEqual(hashlib.sha256(raw_lock).hexdigest(), self.FIXTURE_LOCK_DIGEST)

    def test_payload_scoping(self):
        """Validates that payloads contain only permitted fields and no leaked local/runner state."""
        _, cat_payload = compute_catalog_digest(self.sample_projection)

        # Catalog scope
        self.assertEqual(cat_payload["channel"], 0)
        self.assertEqual(cat_payload["contract"], CONTRACT_CATALOG_DIGEST_PAYLOAD)
        for p in cat_payload["packages"]:
            self.assertEqual(set(p.keys()), {"package_path", "catalog_revision"})

        # Proposal scope
        proposal = create_lock_proposal(
            cat_payload,
            self.sample_env,
            self.sample_gpu,
            self.sample_freshness,
            self.sample_provenance,
        )
        self.assertEqual(proposal["proposal_state"], PROPOSAL_STATE_PENDING)
        self.assertNotIn("lock_approved", proposal)
        self.assertNotIn("selected_gpu", proposal["gpu_evidence"])
        self.assertNotIn("gpu_mode", proposal["gpu_evidence"])
        self.assertEqual(proposal["ready_for_human_review"], True)

        # Lock scope
        decision = {
            "catalog_digest": self.FIXTURE_CATALOG_DIGEST,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": self.FIXTURE_LOCK_PROPOSAL_DIGEST,
            "review_context": {"authority_basis": "EXTERNAL_FOUNDER_GATE"},
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }
        _, _, lock_payload, _ = compute_lock_candidate(proposal, decision, self.sample_eval_time)
        self.assertEqual(
            set(lock_payload.keys()),
            {"catalog_digest", "contract", "environment_locks", "hard_locks", "proposal_digest", "selected_gpu"},
        )


class TestDualFreshness(unittest.TestCase):
    """Validates dual-window freshness enforcement: reviewed_at and evaluation_time_utc."""

    def setUp(self):
        self.tester = TestThreeDigestModel()
        self.tester.setUp()
        self.cat_digest, self.cat_payload = compute_catalog_digest(self.tester.sample_projection)
        self.proposal = create_lock_proposal(
            self.cat_payload,
            self.tester.sample_env,
            self.tester.sample_gpu,
            self.tester.sample_freshness,
            self.tester.sample_provenance,
        )
        self.prop_digest = compute_lock_proposal_digest(self.proposal)
        self.base_decision = {
            "catalog_digest": self.cat_digest,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": self.prop_digest,
            "review_context": {"authority_basis": "EXTERNAL_FOUNDER_GATE"},
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }

    def test_both_in_range_passes(self):
        """reviewed_at in range and evaluation_time in range passes."""
        valid, errors, report = verify_human_decision(
            self.base_decision, self.proposal, evaluation_time_utc="2026-09-22T10:00:00Z"
        )
        self.assertTrue(valid)
        self.assertTrue(report["REVIEW_TIME_VALID"])
        self.assertTrue(report["EVALUATION_TIME_VALID"])
        self.assertTrue(report["FRESHNESS_VALID"])

    def test_reviewed_at_expired_fails(self):
        """reviewed_at > fresh_until fails closed even if evaluation_time is in range."""
        dec = copy.deepcopy(self.base_decision)
        dec["reviewed_at"] = "2026-09-28T00:00:00Z"  # After 2026-09-27T12:00:00Z
        valid, errors, report = verify_human_decision(
            dec, self.proposal, evaluation_time_utc="2026-09-21T15:30:00Z"
        )
        self.assertFalse(valid)
        self.assertFalse(report["REVIEW_TIME_VALID"])
        self.assertTrue(report["EVALUATION_TIME_VALID"])
        self.assertFalse(report["FRESHNESS_VALID"])
        self.assertTrue(any("Proposal expired at review time" in e for e in errors))

    def test_evaluation_time_expired_fails(self):
        """evaluation_time_utc > fresh_until fails closed even if reviewed_at was in range."""
        valid, errors, report = verify_human_decision(
            self.base_decision, self.proposal, evaluation_time_utc="2026-09-28T00:00:00Z"
        )
        self.assertFalse(valid)
        self.assertTrue(report["REVIEW_TIME_VALID"])
        self.assertFalse(report["EVALUATION_TIME_VALID"])
        self.assertFalse(report["FRESHNESS_VALID"])
        self.assertTrue(any("Proposal expired at evaluation time" in e for e in errors))

    def test_backdated_decision_cannot_revive_expired_proposal(self):
        """A historical decision cannot be used today if today is after fresh_until."""
        # Proposal was observed on 2026-09-20, fresh until 2026-09-27T12:00:00Z
        # Decision was recorded in range on 2026-09-21T15:00:00Z
        # Attempting evaluation today (e.g. 2026-10-01) must fail closed.
        valid, errors, report = verify_human_decision(
            self.base_decision, self.proposal, evaluation_time_utc="2026-10-01T00:00:00Z"
        )
        self.assertFalse(valid)
        self.assertFalse(report["FRESHNESS_VALID"])

        # Also test compute_lock_candidate fails closed
        valid_lock, lock_digest, _, errors_lock = compute_lock_candidate(
            self.proposal, self.base_decision, evaluation_time_utc="2026-10-01T00:00:00Z"
        )
        self.assertFalse(valid_lock)
        self.assertIsNone(lock_digest)

    def test_evaluation_time_predates_observation_fails(self):
        """evaluation_time_utc < observed_at fails closed."""
        valid, errors, report = verify_human_decision(
            self.base_decision, self.proposal, evaluation_time_utc="2026-09-19T00:00:00Z"
        )
        self.assertFalse(valid)
        self.assertFalse(report["EVALUATION_TIME_VALID"])
        self.assertTrue(any("Evaluation time predates observation" in e for e in errors))

    def test_invalid_evaluation_timestamp_fails(self):
        """Malformed evaluation timestamp fails closed."""
        valid, errors, report = verify_human_decision(
            self.base_decision, self.proposal, evaluation_time_utc="invalid-timestamp"
        )
        self.assertFalse(valid)
        self.assertFalse(report["EVALUATION_TIME_VALID"])


class TestGPUEvidenceStrictMatrix(unittest.TestCase):
    """Validates strict fail-closed requirements for GPU evidence."""

    def setUp(self):
        self.tester = TestThreeDigestModel()
        self.tester.setUp()
        self.cat_digest, self.cat_payload = compute_catalog_digest(self.tester.sample_projection)

    def test_missing_gpu_mandatory_fields_fail_closed(self):
        """Missing any mandatory field in gpu_evidence fails closed without silent default."""
        mandatory_fields = [
            "status",
            "emulator_revision",
            "projection_sha256",
            "parser_status",
            "candidate_modes",
            "evidence_ready",
        ]
        for field in mandatory_fields:
            gpu = copy.deepcopy(self.tester.sample_gpu)
            del gpu[field]
            with self.subTest(missing_field=field):
                with self.assertRaises(ValueError):
                    create_lock_proposal(
                        self.cat_payload,
                        self.tester.sample_env,
                        gpu,
                        self.tester.sample_freshness,
                        self.tester.sample_provenance,
                    )

    def test_projection_sha256_validation(self):
        """Validates lowercase 64-hex regex requirements for projection_sha256 when evidence_ready=True."""
        bad_hashes = [
            "",                                                                  # empty
            "60c5a10abe62cbbba40f81967647a67f98b0357b5c6e41c422c331a2d810346",   # 63 chars
            "60c5a10abe62cbbba40f81967647a67f98b0357b5c6e41c422c331a2d8103467a",  # 65 chars
            "60C5A10ABE62CBBBA40F81967647A67F98B0357B5C6E41C422C331A2D8103467",  # uppercase hex
            "60c5a10abe62cbbba40f81967647a67f98b0357b5c6e41c422c331a2d81034zz",  # non-hex chars
        ]
        for bad_h in bad_hashes:
            gpu = copy.deepcopy(self.tester.sample_gpu)
            gpu["projection_sha256"] = bad_h
            with self.subTest(bad_hash=bad_h):
                with self.assertRaises(ValueError):
                    create_lock_proposal(
                        self.cat_payload,
                        self.tester.sample_env,
                        gpu,
                        self.tester.sample_freshness,
                        self.tester.sample_provenance,
                    )

    def test_evidence_ready_status_and_parser_requirements(self):
        """evidence_ready=True requires status='PASS_STRICT', parser_status='PASS_STRICT', candidates >= 1."""
        gpu1 = copy.deepcopy(self.tester.sample_gpu)
        gpu1["status"] = "UNAVAILABLE"
        with self.assertRaises(ValueError):
            create_lock_proposal(self.cat_payload, self.tester.sample_env, gpu1, self.tester.sample_freshness, self.tester.sample_provenance)

        gpu2 = copy.deepcopy(self.tester.sample_gpu)
        gpu2["parser_status"] = "AMBIGUOUS"
        with self.assertRaises(ValueError):
            create_lock_proposal(self.cat_payload, self.tester.sample_env, gpu2, self.tester.sample_freshness, self.tester.sample_provenance)

        gpu3 = copy.deepcopy(self.tester.sample_gpu)
        gpu3["candidate_modes"] = []
        with self.assertRaises(ValueError):
            create_lock_proposal(self.cat_payload, self.tester.sample_env, gpu3, self.tester.sample_freshness, self.tester.sample_provenance)

    def test_emulator_revision_binding_to_environment(self):
        """gpu_evidence.emulator_revision != environment.emulator_revision fails closed."""
        gpu = copy.deepcopy(self.tester.sample_gpu)
        gpu["emulator_revision"] = "37.1.10"  # Diverges from environment 37.1.11
        with self.assertRaises(ValueError):
            create_lock_proposal(
                self.cat_payload,
                self.tester.sample_env,
                gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_emulator_revision_binding_to_hard_lock(self):
        """environment.emulator_revision != hard_locks['emulator'] fails closed."""
        env = copy.deepcopy(self.tester.sample_env)
        env["emulator_revision"] = "37.1.12"
        gpu = copy.deepcopy(self.tester.sample_gpu)
        gpu["emulator_revision"] = "37.1.12"
        # Diverges from hard_locks emulator revision "37.1.11"
        with self.assertRaises(ValueError):
            create_lock_proposal(
                self.cat_payload,
                env,
                gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_proposal_with_evidence_not_ready_diagnostics(self):
        """evidence_ready=False creates diagnostic proposal with ready_for_human_review=False."""
        gpu = copy.deepcopy(self.tester.sample_gpu)
        gpu["evidence_ready"] = False
        gpu["status"] = "UNAVAILABLE"
        gpu["parser_status"] = "UNAVAILABLE"
        gpu["candidate_modes"] = []
        gpu["projection_sha256"] = ""

        prop = create_lock_proposal(
            self.cat_payload,
            self.tester.sample_env,
            gpu,
            self.tester.sample_freshness,
            self.tester.sample_provenance,
        )
        self.assertFalse(prop["ready_for_human_review"])
        self.assertEqual(prop["proposal_state"], PROPOSAL_STATE_PENDING)

        # Digest can still be computed
        prop_digest = compute_lock_proposal_digest(prop)
        self.assertIsNotNone(prop_digest)

        # APPROVE decision fails on non-ready proposal
        dec = {
            "catalog_digest": self.cat_digest,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": prop_digest,
            "review_context": {"authority_basis": "EXTERNAL_FOUNDER_GATE"},
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }
        valid, errors, report = verify_human_decision(dec, prop, self.tester.sample_eval_time)
        self.assertFalse(valid)
        self.assertTrue(any("ready_for_human_review is False" in e for e in errors))

        # Lock candidate cannot be computed
        valid_lock, lock_digest, _, errors_lock = compute_lock_candidate(
            prop, dec, self.tester.sample_eval_time
        )
        self.assertFalse(valid_lock)
        self.assertIsNone(lock_digest)


class TestDirectCatalogPayloadBypass(unittest.TestCase):
    """Directly calls create_lock_proposal with adversarial payloads to prove bypass is closed."""

    def setUp(self):
        self.tester = TestThreeDigestModel()
        self.tester.setUp()
        _, self.cat_payload = compute_catalog_digest(self.tester.sample_projection)

    def test_duplicate_package_in_payload_fails_closed(self):
        """Duplicate package entry in external catalog payload fails closed."""
        payload = copy.deepcopy(self.cat_payload)
        payload["packages"].append(copy.deepcopy(payload["packages"][0]))
        with self.assertRaises(ValueError):
            create_lock_proposal(
                payload,
                self.tester.sample_env,
                self.tester.sample_gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_wrong_package_in_payload_fails_closed(self):
        """Package not in HARD_LOCK_PACKAGES fails closed."""
        payload = copy.deepcopy(self.cat_payload)
        payload["packages"][0]["package_path"] = "wrong;package;path"
        with self.assertRaises(ValueError):
            create_lock_proposal(
                payload,
                self.tester.sample_env,
                self.tester.sample_gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_extra_package_in_payload_fails_closed(self):
        """Extra package outside the 5 HARD_LOCK_PACKAGES fails closed."""
        payload = copy.deepcopy(self.cat_payload)
        payload["packages"].append({
            "catalog_revision": "1.0",
            "package_path": "extra;package",
        })
        with self.assertRaises(ValueError):
            create_lock_proposal(
                payload,
                self.tester.sample_env,
                self.tester.sample_gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_missing_package_in_payload_fails_closed(self):
        """Missing package in external catalog payload fails closed."""
        payload = copy.deepcopy(self.cat_payload)
        payload["packages"] = payload["packages"][:-1]
        with self.assertRaises(ValueError):
            create_lock_proposal(
                payload,
                self.tester.sample_env,
                self.tester.sample_gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_empty_revision_in_payload_fails_closed(self):
        """Empty catalog_revision in external catalog payload fails closed."""
        payload = copy.deepcopy(self.cat_payload)
        payload["packages"][0]["catalog_revision"] = "   "
        with self.assertRaises(ValueError):
            create_lock_proposal(
                payload,
                self.tester.sample_env,
                self.tester.sample_gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_channel_non_zero_fails_closed(self):
        """channel != 0 fails closed."""
        payload = copy.deepcopy(self.cat_payload)
        payload["channel"] = 1
        with self.assertRaises(ValueError):
            create_lock_proposal(
                payload,
                self.tester.sample_env,
                self.tester.sample_gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_wrong_contract_fails_closed(self):
        """Wrong contract string fails closed."""
        payload = copy.deepcopy(self.cat_payload)
        payload["contract"] = "WRONG_CONTRACT"
        with self.assertRaises(ValueError):
            create_lock_proposal(
                payload,
                self.tester.sample_env,
                self.tester.sample_gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_unexpected_package_field_fails_closed(self):
        """Unexpected key in package entry fails closed."""
        payload = copy.deepcopy(self.cat_payload)
        payload["packages"][0]["unexpected_field"] = "malicious"
        with self.assertRaises(ValueError):
            create_lock_proposal(
                payload,
                self.tester.sample_env,
                self.tester.sample_gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )


class TestEnvironmentProvenanceCoherence(unittest.TestCase):
    """Validates runner coherence between environment and provenance."""

    def setUp(self):
        self.tester = TestThreeDigestModel()
        self.tester.setUp()
        _, self.cat_payload = compute_catalog_digest(self.tester.sample_projection)

    def test_runner_image_label_mismatch_fails_closed(self):
        """Different runner_image_label in environment and provenance fails closed."""
        prov = copy.deepcopy(self.tester.sample_provenance)
        prov["runner_image_label"] = "ubuntu-22.04"  # Env has ubuntu-24.04
        with self.assertRaises(ValueError):
            create_lock_proposal(
                self.cat_payload,
                self.tester.sample_env,
                self.tester.sample_gpu,
                self.tester.sample_freshness,
                prov,
            )

    def test_runner_image_version_mismatch_fails_closed(self):
        """Different runner_image_version in environment and provenance fails closed."""
        prov = copy.deepcopy(self.tester.sample_provenance)
        prov["runner_image_version"] = "20240901.2"  # Env has 20240901.1
        with self.assertRaises(ValueError):
            create_lock_proposal(
                self.cat_payload,
                self.tester.sample_env,
                self.tester.sample_gpu,
                self.tester.sample_freshness,
                prov,
            )


class TestHumanDecisionClosedContract(unittest.TestCase):
    """Validates closed schema, mandatory review_context, and authority reporting."""

    def setUp(self):
        self.tester = TestThreeDigestModel()
        self.tester.setUp()
        self.cat_digest, self.cat_payload = compute_catalog_digest(self.tester.sample_projection)
        self.proposal = create_lock_proposal(
            self.cat_payload,
            self.tester.sample_env,
            self.tester.sample_gpu,
            self.tester.sample_freshness,
            self.tester.sample_provenance,
        )
        self.prop_digest = compute_lock_proposal_digest(self.proposal)
        self.base_decision = {
            "catalog_digest": self.cat_digest,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": self.prop_digest,
            "review_context": {"authority_basis": "EXTERNAL_FOUNDER_GATE"},
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }

    def test_missing_review_context_fails_closed(self):
        """HumanDecision missing review_context fails closed."""
        dec = copy.deepcopy(self.base_decision)
        del dec["review_context"]
        valid, errors, report = verify_human_decision(dec, self.proposal, self.tester.sample_eval_time)
        self.assertFalse(valid)
        self.assertTrue(any("Missing review_context" in e for e in errors))

    def test_empty_review_context_fails_closed(self):
        """HumanDecision with empty review_context dict fails closed."""
        dec = copy.deepcopy(self.base_decision)
        dec["review_context"] = {}
        valid, errors, report = verify_human_decision(dec, self.proposal, self.tester.sample_eval_time)
        self.assertFalse(valid)
        self.assertTrue(any("non-empty dictionary" in e for e in errors))

    def test_review_context_wrong_type_fails_closed(self):
        """HumanDecision with non-dict review_context fails closed."""
        dec = copy.deepcopy(self.base_decision)
        dec["review_context"] = "FOUNDER_APPROVAL"
        valid, errors, report = verify_human_decision(dec, self.proposal, self.tester.sample_eval_time)
        self.assertFalse(valid)
        self.assertTrue(any("non-empty dictionary" in e for e in errors))

    def test_unexpected_top_level_field_fails_closed(self):
        """Closed schema rejects unexpected top-level fields in HumanDecision."""
        dec = copy.deepcopy(self.base_decision)
        dec["extra_field"] = "malicious_injection"
        valid, errors, report = verify_human_decision(dec, self.proposal, self.tester.sample_eval_time)
        self.assertFalse(valid)
        self.assertTrue(any("Unexpected field(s)" in e for e in errors))

    def test_human_authority_externally_required_always_true(self):
        """HUMAN_AUTHORITY_EXTERNALLY_REQUIRED=True is always reported."""
        valid, errors, report = verify_human_decision(self.base_decision, self.proposal, self.tester.sample_eval_time)
        self.assertTrue(valid)
        self.assertTrue(report.get("HUMAN_AUTHORITY_EXTERNALLY_REQUIRED"))

    def test_approve_with_valid_and_invalid_gpu(self):
        """APPROVE requires valid GPU candidate, rejects non-candidate or missing GPU."""
        # Missing GPU
        dec_no_gpu = copy.deepcopy(self.base_decision)
        del dec_no_gpu["selected_gpu"]
        valid, errors, _ = verify_human_decision(dec_no_gpu, self.proposal, self.tester.sample_eval_time)
        self.assertFalse(valid)
        self.assertTrue(any("selected_gpu is mandatory" in e for e in errors))

        # Invalid GPU
        dec_bad_gpu = copy.deepcopy(self.base_decision)
        dec_bad_gpu["selected_gpu"] = "hardware_direct"
        valid, errors, _ = verify_human_decision(dec_bad_gpu, self.proposal, self.tester.sample_eval_time)
        self.assertFalse(valid)
        self.assertTrue(any("not in proposal candidate_modes" in e for e in errors))

    def test_reject_decision(self):
        """REJECT allows None/omitted GPU, rejects when GPU is provided."""
        dec_reject = copy.deepcopy(self.base_decision)
        dec_reject["decision"] = "REJECT"
        dec_reject["selected_gpu"] = None
        valid, errors, report = verify_human_decision(dec_reject, self.proposal, self.tester.sample_eval_time)
        self.assertTrue(valid)
        self.assertTrue(report["SELECTED_GPU_VALID"])

        # REJECT with selected_gpu fails
        dec_reject_with_gpu = copy.deepcopy(self.base_decision)
        dec_reject_with_gpu["decision"] = "REJECT"
        dec_reject_with_gpu["selected_gpu"] = "swiftshader_indirect"
        valid, errors, _ = verify_human_decision(dec_reject_with_gpu, self.proposal, self.tester.sample_eval_time)
        self.assertFalse(valid)
        self.assertTrue(any("selected_gpu must be None" in e for e in errors))


class TestMutationMatrix(unittest.TestCase):
    """Validates that targeted mutations cause expected digest changes or rejections."""

    def setUp(self):
        self.tester = TestThreeDigestModel()
        self.tester.setUp()
        self.cat_digest, self.cat_payload = compute_catalog_digest(self.tester.sample_projection)
        self.proposal = create_lock_proposal(
            self.cat_payload,
            self.tester.sample_env,
            self.tester.sample_gpu,
            self.tester.sample_freshness,
            self.tester.sample_provenance,
        )
        self.prop_digest = compute_lock_proposal_digest(self.proposal)
        self.decision = {
            "catalog_digest": self.cat_digest,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": self.prop_digest,
            "review_context": {"authority_basis": "EXTERNAL_FOUNDER_GATE"},
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }
        _, self.lock_digest, self.lock_payload, _ = compute_lock_candidate(
            self.proposal, self.decision, self.tester.sample_eval_time
        )

    def test_catalog_package_revision_mutation(self):
        """Mutating a catalog package revision changes all 3 dependent digests."""
        proj = copy.deepcopy(self.tester.sample_projection)
        proj["packages"][1]["catalog_revision"] = "37.1.12"  # emulator revision changed
        env = copy.deepcopy(self.tester.sample_env)
        env["emulator_revision"] = "37.1.12"
        gpu = copy.deepcopy(self.tester.sample_gpu)
        gpu["emulator_revision"] = "37.1.12"

        new_cat_digest, new_cat_payload = compute_catalog_digest(proj)
        self.assertNotEqual(new_cat_digest, self.cat_digest)

        new_prop = create_lock_proposal(
            new_cat_payload,
            env,
            gpu,
            self.tester.sample_freshness,
            self.tester.sample_provenance,
        )
        new_prop_digest = compute_lock_proposal_digest(new_prop)
        self.assertNotEqual(new_prop_digest, self.prop_digest)

        new_decision = copy.deepcopy(self.decision)
        new_decision["catalog_digest"] = new_cat_digest
        new_decision["proposal_digest"] = new_prop_digest

        _, new_lock_digest, _, _ = compute_lock_candidate(
            new_prop, new_decision, self.tester.sample_eval_time
        )
        self.assertNotEqual(new_lock_digest, self.lock_digest)

    def test_gpu_candidate_mutation(self):
        """Mutating GPU candidates changes proposal digest and lock digest, but catalog digest is unchanged."""
        gpu = copy.deepcopy(self.tester.sample_gpu)
        gpu["candidate_modes"] = ["auto-no-window", "off", "swiftshader_indirect", "angle_indirect"]

        new_prop = create_lock_proposal(
            self.cat_payload,
            self.tester.sample_env,
            gpu,
            self.tester.sample_freshness,
            self.tester.sample_provenance,
        )
        new_prop_digest = compute_lock_proposal_digest(new_prop)
        self.assertNotEqual(new_prop_digest, self.prop_digest)
        self.assertEqual(new_prop["catalog_digest"], self.cat_digest)

    def test_projection_sha256_mutation(self):
        """Mutating projection_sha256 changes proposal digest."""
        gpu = copy.deepcopy(self.tester.sample_gpu)
        gpu["projection_sha256"] = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"

        new_prop = create_lock_proposal(
            self.cat_payload,
            self.tester.sample_env,
            gpu,
            self.tester.sample_freshness,
            self.tester.sample_provenance,
        )
        new_prop_digest = compute_lock_proposal_digest(new_prop)
        self.assertNotEqual(new_prop_digest, self.prop_digest)

    def test_selected_gpu_mutation(self):
        """Mutating selected GPU changes LOCK_DIGEST but not CATALOG_DIGEST or LOCK_PROPOSAL_DIGEST."""
        new_decision = copy.deepcopy(self.decision)
        new_decision["selected_gpu"] = "auto-no-window"

        _, new_lock_digest, _, _ = compute_lock_candidate(
            self.proposal, new_decision, self.tester.sample_eval_time
        )
        self.assertNotEqual(new_lock_digest, self.lock_digest)

        # Catalog and Proposal digests remain unaffected
        self.assertEqual(self.proposal["catalog_digest"], self.cat_digest)
        self.assertEqual(compute_lock_proposal_digest(self.proposal), self.prop_digest)

    def test_review_context_mutation_does_not_alter_lock_digest(self):
        """Mutating review_context does NOT change LOCK_DIGEST because it is not part of lock payload."""
        dec_mutated = copy.deepcopy(self.decision)
        dec_mutated["review_context"] = {"audit_id": "AUDIT-002-R1-RUNNER-99"}

        valid, new_lock_digest, new_lock_payload, _ = compute_lock_candidate(
            self.proposal, dec_mutated, self.tester.sample_eval_time
        )
        self.assertTrue(valid)
        self.assertEqual(new_lock_digest, self.lock_digest)
        self.assertEqual(new_lock_payload, self.lock_payload)

    def test_ready_for_human_review_tampering_rejected(self):
        """Manually modifying ready_for_human_review when evidence_ready=False is rejected by validator."""
        gpu = copy.deepcopy(self.tester.sample_gpu)
        gpu["evidence_ready"] = False
        gpu["status"] = "UNAVAILABLE"
        gpu["parser_status"] = "UNAVAILABLE"
        gpu["candidate_modes"] = []
        gpu["projection_sha256"] = ""

        prop = create_lock_proposal(
            self.cat_payload,
            self.tester.sample_env,
            gpu,
            self.tester.sample_freshness,
            self.tester.sample_provenance,
        )
        # Attempt to tamper: force ready_for_human_review = True
        prop["ready_for_human_review"] = True

        with self.assertRaises(ValueError) as ctx:
            validate_lock_proposal(prop)
        self.assertIn("ready_for_human_review must be False when evidence_ready=False", str(ctx.exception))

    def test_hard_locks_tampering_rejected(self):
        """Modifying hard_locks in proposal without matching catalog_digest fails validate_lock_proposal."""
        prop = copy.deepcopy(self.proposal)
        prop["hard_locks"][0]["revision"] = "99.0.0"

        with self.assertRaises(ValueError) as ctx:
            validate_lock_proposal(prop)
        self.assertIn("catalog_digest", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
