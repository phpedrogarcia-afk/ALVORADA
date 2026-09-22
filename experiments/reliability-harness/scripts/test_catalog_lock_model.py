#!/usr/bin/env python3
"""
ALVORADA — Comprehensive Unit & Mutation Test Suite for Three-Digest Lock Model
Contract Version: RECOVERY-G1-002

Validates:
1. CATALOG_DIGEST, LOCK_PROPOSAL_DIGEST, and LOCK_DIGEST three-way separation.
2. Pre-computed static SHA-256 fixtures verified with independent second-path byte builder.
3. Strict payload scoping (no leakage of local paths, installed revisions, or premature approvals).
4. Mutation matrix (catalog revision, GPU candidates, selected GPU, runner image, timestamps).
5. Comprehensive fail-closed matrix (missing/extra packages, ambiguity, expired proposals, invalid candidates).
6. Human authority is external (HUMAN_AUTHORITY_EXTERNALLY_REQUIRED=True, LOCK_CANDIDATE_COMPUTED).
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
    create_catalog_digest_payload,
    compute_catalog_digest,
    create_lock_proposal,
    compute_lock_proposal_digest,
    verify_human_decision,
    compute_lock_candidate,
)


class TestThreeDigestModel(unittest.TestCase):
    """Validates three-digest separation, static fixtures, and independent second path."""

    FIXTURE_CATALOG_DIGEST = "6c27ebaa82b34492b4f99c8ef52e63fc76b7ac7da70b02208f42045b884e0677"
    FIXTURE_LOCK_PROPOSAL_DIGEST = "fbba401d143b8a079b120e52619ef82af4595364352f40e1b41e38854fc2e43e"
    FIXTURE_LOCK_DIGEST = "a5ea5a674d6703520b8b79c760877e4466183b16c2027591ad70d4b6dd2a044f"

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

    def test_three_digests_computed_and_distinct(self):
        """Validates that CATALOG_DIGEST, LOCK_PROPOSAL_DIGEST, and LOCK_DIGEST are distinct."""
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

        decision = {
            "catalog_digest": cat_digest,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": prop_digest,
            "review_context": {"reviewer_identity_type": "FOUNDER_EXTERNAL"},
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }
        is_valid, lock_digest, lock_payload, errors = compute_lock_candidate(proposal, decision)
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
            b'"provenance":{"catalog_run_id":"35540374123","repository_commit_sha":"43018b1f9b14cb9e580d2157e6cb623ee18de0d1","runner_image_label":"ubuntu-24.04","runner_image_version":"20240901.1"}'
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
            b'"proposal_digest":"fbba401d143b8a079b120e52619ef82af4595364352f40e1b41e38854fc2e43e",'
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

        # Lock scope
        decision = {
            "catalog_digest": self.FIXTURE_CATALOG_DIGEST,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": self.FIXTURE_LOCK_PROPOSAL_DIGEST,
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }
        _, _, lock_payload, _ = compute_lock_candidate(proposal, decision)
        self.assertEqual(
            set(lock_payload.keys()),
            {"catalog_digest", "contract", "environment_locks", "hard_locks", "proposal_digest", "selected_gpu"},
        )


class TestMutationMatrix(unittest.TestCase):
    """Validates that targeted mutations cause expected digest changes."""

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
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }
        _, self.lock_digest, self.lock_payload, _ = compute_lock_candidate(self.proposal, self.decision)

    def test_catalog_package_revision_mutation(self):
        """Mutating a catalog package revision changes all 3 dependent digests."""
        proj = copy.deepcopy(self.tester.sample_projection)
        proj["packages"][1]["catalog_revision"] = "37.1.12"  # emulator revision changed

        new_cat_digest, new_cat_payload = compute_catalog_digest(proj)
        self.assertNotEqual(new_cat_digest, self.cat_digest)

        new_prop = create_lock_proposal(
            new_cat_payload,
            self.tester.sample_env,
            self.tester.sample_gpu,
            self.tester.sample_freshness,
            self.tester.sample_provenance,
        )
        new_prop_digest = compute_lock_proposal_digest(new_prop)
        self.assertNotEqual(new_prop_digest, self.prop_digest)

        new_decision = copy.deepcopy(self.decision)
        new_decision["catalog_digest"] = new_cat_digest
        new_decision["proposal_digest"] = new_prop_digest

        _, new_lock_digest, _, _ = compute_lock_candidate(new_prop, new_decision)
        self.assertNotEqual(new_lock_digest, self.lock_digest)

    def test_gpu_candidate_mutation(self):
        """Mutating GPU candidates changes proposal digest and lock digest, but catalog digest is unchanged."""
        gpu = copy.deepcopy(self.tester.sample_gpu)
        gpu["candidate_modes"] = ["auto-no-window", "off"]  # removed swiftshader_indirect

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

    def test_selected_gpu_mutation(self):
        """Mutating selected GPU changes LOCK_DIGEST but not CATALOG_DIGEST or LOCK_PROPOSAL_DIGEST."""
        new_decision = copy.deepcopy(self.decision)
        new_decision["selected_gpu"] = "auto-no-window"

        _, new_lock_digest, _, _ = compute_lock_candidate(self.proposal, new_decision)
        self.assertNotEqual(new_lock_digest, self.lock_digest)

        # Catalog and Proposal digests remain unaffected
        self.assertEqual(self.proposal["catalog_digest"], self.cat_digest)
        self.assertEqual(compute_lock_proposal_digest(self.proposal), self.prop_digest)

    def test_runner_image_mutation(self):
        """Mutating runner image changes proposal digest but not catalog digest."""
        env = copy.deepcopy(self.tester.sample_env)
        env["runner_image_label"] = "ubuntu-24.04-custom"

        new_prop = create_lock_proposal(
            self.cat_payload,
            env,
            self.tester.sample_gpu,
            self.tester.sample_freshness,
            self.tester.sample_provenance,
        )
        new_prop_digest = compute_lock_proposal_digest(new_prop)
        self.assertNotEqual(new_prop_digest, self.prop_digest)
        self.assertEqual(new_prop["catalog_digest"], self.cat_digest)

    def test_observed_at_mutation(self):
        """Mutating observed_at changes proposal digest."""
        freshness = copy.deepcopy(self.tester.sample_freshness)
        freshness["observed_at"] = "2026-09-20T13:00:00Z"
        freshness["fresh_until"] = "2026-09-27T13:00:00Z"

        new_prop = create_lock_proposal(
            self.cat_payload,
            self.tester.sample_env,
            self.tester.sample_gpu,
            freshness,
            self.tester.sample_provenance,
        )
        new_prop_digest = compute_lock_proposal_digest(new_prop)
        self.assertNotEqual(new_prop_digest, self.prop_digest)

    def test_nonsemantic_metadata_isolation(self):
        """Metadata outside the canonical payload does not alter canonical digests."""
        proj = copy.deepcopy(self.tester.sample_projection)
        proj["metadata"] = {"ci_execution_tag": "run_12345", "random_seed": "abc"}

        cat_digest, _ = compute_catalog_digest(proj)
        self.assertEqual(cat_digest, self.cat_digest)


class TestFailClosedMatrix(unittest.TestCase):
    """Validates fail-closed behavior on invalid, ambiguous, or expired inputs."""

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

    def test_missing_package_fails_closed(self):
        """Missing a required hard lock package fails closed."""
        proj = copy.deepcopy(self.tester.sample_projection)
        proj["packages"] = [p for p in proj["packages"] if p["package_path"] != "emulator"]
        with self.assertRaises(ValueError):
            compute_catalog_digest(proj)

    def test_extra_package_fails_closed(self):
        """Extra package outside the 5 HARD_LOCK packages fails closed."""
        proj = copy.deepcopy(self.tester.sample_projection)
        proj["packages"].append({
            "catalog_revision": "1.0",
            "package_path": "extras;unapproved;package",
            "state": "PRESENT_MATCHING_CATALOG",
        })
        with self.assertRaises(ValueError):
            compute_catalog_digest(proj)

    def test_duplicate_package_fails_closed(self):
        """Duplicate package entry fails closed."""
        proj = copy.deepcopy(self.tester.sample_projection)
        proj["packages"].append(copy.deepcopy(proj["packages"][0]))
        with self.assertRaises(ValueError):
            compute_catalog_digest(proj)

    def test_missing_catalog_revision_fails_closed(self):
        """Missing or empty catalog_revision fails closed."""
        proj = copy.deepcopy(self.tester.sample_projection)
        proj["packages"][0]["catalog_revision"] = ""
        with self.assertRaises(ValueError):
            compute_catalog_digest(proj)

    def test_incomplete_or_ambiguous_projection_fails_closed(self):
        """Incomplete or ambiguous projection fails closed."""
        proj_incomp = copy.deepcopy(self.tester.sample_projection)
        proj_incomp["is_complete"] = False
        with self.assertRaises(ValueError):
            compute_catalog_digest(proj_incomp)

        proj_amb = copy.deepcopy(self.tester.sample_projection)
        proj_amb["has_ambiguity"] = True
        with self.assertRaises(ValueError):
            compute_catalog_digest(proj_amb)

    def test_local_path_in_environment_fails_closed(self):
        """Local path in environment fails closed."""
        env = copy.deepcopy(self.tester.sample_env)
        env["sdk_root"] = "C:\\Android\\sdk"
        with self.assertRaises(ValueError):
            create_lock_proposal(
                self.cat_payload,
                env,
                self.tester.sample_gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_invalid_jdk_major_fails_closed(self):
        """jdk_major other than integer 17 fails closed."""
        env = copy.deepcopy(self.tester.sample_env)
        env["jdk_major"] = 21
        with self.assertRaises(ValueError):
            create_lock_proposal(
                self.cat_payload,
                env,
                self.tester.sample_gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_gpu_selection_in_proposal_fails_closed(self):
        """Premature selected_gpu or gpu_mode in proposal fails closed."""
        gpu1 = copy.deepcopy(self.tester.sample_gpu)
        gpu1["selected_gpu"] = "swiftshader_indirect"
        with self.assertRaises(ValueError):
            create_lock_proposal(
                self.cat_payload,
                self.tester.sample_env,
                gpu1,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

        gpu2 = copy.deepcopy(self.tester.sample_gpu)
        gpu2["gpu_mode"] = "swiftshader_indirect"
        with self.assertRaises(ValueError):
            create_lock_proposal(
                self.cat_payload,
                self.tester.sample_env,
                gpu2,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_gpu_candidates_empty_when_evidence_ready_fails_closed(self):
        """evidence_ready=True with empty candidate_modes fails closed."""
        gpu = copy.deepcopy(self.tester.sample_gpu)
        gpu["candidate_modes"] = []
        with self.assertRaises(ValueError):
            create_lock_proposal(
                self.cat_payload,
                self.tester.sample_env,
                gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_gpu_parser_not_pass_strict_fails_closed(self):
        """evidence_ready=True with parser_status != PASS_STRICT fails closed."""
        gpu = copy.deepcopy(self.tester.sample_gpu)
        gpu["parser_status"] = "FAIL_PARSE"
        with self.assertRaises(ValueError):
            create_lock_proposal(
                self.cat_payload,
                self.tester.sample_env,
                gpu,
                self.tester.sample_freshness,
                self.tester.sample_provenance,
            )

    def test_selected_gpu_not_candidate_fails_closed(self):
        """Decision selecting a GPU not in candidate_modes fails closed."""
        decision = {
            "catalog_digest": self.cat_digest,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": compute_lock_proposal_digest(self.proposal),
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "hardware_direct",  # Not in candidate_modes
        }
        valid, errors, report = verify_human_decision(decision, self.proposal)
        self.assertFalse(valid)
        self.assertTrue(any("not in proposal candidate_modes" in e for e in errors))

    def test_approve_missing_selected_gpu_fails_closed(self):
        """APPROVE decision without selected_gpu fails closed."""
        decision = {
            "catalog_digest": self.cat_digest,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": compute_lock_proposal_digest(self.proposal),
            "reviewed_at": "2026-09-21T15:00:00Z",
        }
        valid, errors, report = verify_human_decision(decision, self.proposal)
        self.assertFalse(valid)
        self.assertTrue(any("selected_gpu is mandatory" in e for e in errors))

    def test_reject_with_selected_gpu_fails_closed(self):
        """REJECT decision with selected_gpu fails closed."""
        decision = {
            "catalog_digest": self.cat_digest,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "REJECT",
            "proposal_digest": compute_lock_proposal_digest(self.proposal),
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }
        valid, errors, report = verify_human_decision(decision, self.proposal)
        self.assertFalse(valid)
        self.assertTrue(any("selected_gpu must be None" in e for e in errors))

    def test_proposal_digest_mismatch_fails_closed(self):
        """Decision with wrong proposal_digest fails closed."""
        decision = {
            "catalog_digest": self.cat_digest,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": "0000000000000000000000000000000000000000000000000000000000000000",
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }
        valid, errors, report = verify_human_decision(decision, self.proposal)
        self.assertFalse(valid)
        self.assertTrue(any("proposal_digest mismatch" in e for e in errors))

    def test_catalog_digest_mismatch_fails_closed(self):
        """Decision with wrong catalog_digest fails closed."""
        decision = {
            "catalog_digest": "1111111111111111111111111111111111111111111111111111111111111111",
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": compute_lock_proposal_digest(self.proposal),
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }
        valid, errors, report = verify_human_decision(decision, self.proposal)
        self.assertFalse(valid)
        self.assertTrue(any("catalog_digest mismatch" in e for e in errors))

    def test_expired_proposal_fails_closed(self):
        """Decision reviewed after fresh_until fails closed."""
        decision = {
            "catalog_digest": self.cat_digest,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": compute_lock_proposal_digest(self.proposal),
            "reviewed_at": "2026-09-28T00:00:00Z",  # Fresh until 2026-09-27T12:00:00Z
            "selected_gpu": "swiftshader_indirect",
        }
        valid, errors, report = verify_human_decision(decision, self.proposal)
        self.assertFalse(valid)
        self.assertTrue(any("Proposal expired" in e for e in errors))

    def test_freshness_invariants_fail_closed(self):
        """fresh_until <= observed_at or delta != 7 days fails closed."""
        fresh1 = copy.deepcopy(self.tester.sample_freshness)
        fresh1["fresh_until"] = fresh1["observed_at"]
        with self.assertRaises(ValueError):
            create_lock_proposal(
                self.cat_payload,
                self.tester.sample_env,
                self.tester.sample_gpu,
                fresh1,
                self.tester.sample_provenance,
            )

        fresh2 = copy.deepcopy(self.tester.sample_freshness)
        fresh2["fresh_until"] = "2026-09-25T12:00:00Z"  # 5 days instead of 7
        with self.assertRaises(ValueError):
            create_lock_proposal(
                self.cat_payload,
                self.tester.sample_env,
                self.tester.sample_gpu,
                fresh2,
                self.tester.sample_provenance,
            )


class TestAuthorityAndGovernanceInvariants(unittest.TestCase):
    """Validates that authority is strictly external and cannot be granted by library."""

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
        self.decision = {
            "catalog_digest": self.cat_digest,
            "contract": CONTRACT_HUMAN_DECISION,
            "decision": "APPROVE",
            "proposal_digest": compute_lock_proposal_digest(self.proposal),
            "reviewed_at": "2026-09-21T15:00:00Z",
            "selected_gpu": "swiftshader_indirect",
        }

    def test_human_authority_externally_required_invariant(self):
        """verify_human_decision always reports HUMAN_AUTHORITY_EXTERNALLY_REQUIRED=True."""
        valid, errors, report = verify_human_decision(self.decision, self.proposal)
        self.assertTrue(valid)
        self.assertTrue(report.get("HUMAN_AUTHORITY_EXTERNALLY_REQUIRED"))

    def test_lock_candidate_computed_not_approved(self):
        """compute_lock_candidate computes a candidate, never grants approval authority."""
        valid, lock_digest, lock_payload, errors = compute_lock_candidate(self.proposal, self.decision)
        self.assertTrue(valid)
        self.assertIsNotNone(lock_digest)
        # Lock payload contains contract and digests, no approval flags
        self.assertEqual(lock_payload["contract"], CONTRACT_LOCK_PAYLOAD)
        self.assertNotIn("lock_approved", lock_payload)
        self.assertNotIn("approved_by", lock_payload)


if __name__ == "__main__":
    unittest.main()
