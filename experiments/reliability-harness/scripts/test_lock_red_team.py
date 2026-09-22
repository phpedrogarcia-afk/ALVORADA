#!/usr/bin/env python3
"""
ALVORADA — Adversarial Red-Team Verification Suite for Catalog Lock & Runner
Campaign: ALVORADA G1 POST-FOUNDER-APPROVAL EXECUTION CAMPAIGN 001
Auditor Role: LOCK_RED_TEAM

Comprehensive red-team adversarial suite testing 9 exploit vectors against:
- catalog_lock_model.py
- lock_runner.py
- ALVORADA_HUMAN_LOCK_DECISION_V1
- ALVORADA_LOCK_PAYLOAD_V1 (Canonical LOCK_DIGEST: ac243a03caca0333eec85721cbd27f828a001c3b19ed80d7994e33589f065f05)

Vectors:
1. selected_gpu substitution ('host', 'lavapipe', 'auto', 'rogue_mode')
2. package revision substitution (altering emulator or platform revision in hard_locks)
3. proposal digest substitution (tampering with proposal_digest)
4. catalog digest substitution (tampering with catalog_digest)
5. decision tampering (altering decision to REJECT or forging review_context/decision_statement)
6. expired evaluation (evaluating at evaluation_time_utc > fresh_until or reviewed_at > evaluation_time_utc)
7. extra package in hard_locks (injecting 6th package)
8. missing package in hard_locks (removing one of the 5 required packages)
9. environment drift (altering jdk_major or emulator_revision in environment_locks)
"""

import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from catalog_core import canonicalize_json_v1, hash_canonical_json_v1
from catalog_lock_model import (
    CONTRACT_HUMAN_DECISION,
    CONTRACT_LOCK_PAYLOAD,
    CONTRACT_LOCK_PROPOSAL_V2,
    compute_lock_candidate,
    compute_lock_proposal_digest,
    validate_lock_proposal,
    verify_human_decision,
)
from lock_runner import (
    EXTERNAL_FOUNDER_DECISION,
    materialize_human_decision,
    materialize_lock_payload,
    run_lock_pipeline,
)
from proposal_assembly_runner import verify_directory_checksums

CANONICAL_LOCK_DIGEST = "ac243a03caca0333eec85721cbd27f828a001c3b19ed80d7994e33589f065f05"
CANONICAL_PROPOSAL_DIGEST = "5517290ec9b90cdcbc13ad34a1228a1ff422f2a5c2326d622e9f2ae249b411b4"
CANONICAL_CATALOG_DIGEST = "e9148d7bcdb5124182f87787a78899845aa9a60aefbe5c4bc581539201b4f6ed"
CANONICAL_DECISION_DIGEST = "5d240bb22205000c5e805fba1c45a99b015e412bebadeb508f88236de74bc5b7"
CANONICAL_EVAL_TIME = "2026-09-22T14:48:00Z"


class TestLockRedTeam(unittest.TestCase):
    """Adversarial Red-Team Verification Suite for Catalog Lock Model and Runner."""

    @classmethod
    def setUpClass(cls):
        cls.evidence_dir = os.path.join(os.path.dirname(SCRIPTS_DIR), "evidence")
        cls.prop_json_path = os.path.join(cls.evidence_dir, "lock-proposal", "lock-proposal.json")
        cls.dec_json_path = os.path.join(cls.evidence_dir, "human-decision", "human-lock-decision.json")
        cls.lock_json_path = os.path.join(cls.evidence_dir, "lock", "lock.json")

        with open(cls.prop_json_path, "r", encoding="utf-8") as f:
            cls.canonical_proposal = json.load(f)
        with open(cls.dec_json_path, "r", encoding="utf-8") as f:
            cls.canonical_decision = json.load(f)
        with open(cls.lock_json_path, "r", encoding="utf-8") as f:
            cls.canonical_lock = json.load(f)

        # Sanity check baseline digests
        assert hash_canonical_json_v1(cls.canonical_lock) == CANONICAL_LOCK_DIGEST
        assert compute_lock_proposal_digest(cls.canonical_proposal) == CANONICAL_PROPOSAL_DIGEST
        assert cls.canonical_proposal["catalog_digest"] == CANONICAL_CATALOG_DIGEST
        assert hashlib.sha256(canonicalize_json_v1(cls.canonical_decision)).hexdigest() == CANONICAL_DECISION_DIGEST

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="alvorada_red_team_")
        self.prop_dir = os.path.join(self.temp_dir, "lock-proposal")
        self.dec_dir = os.path.join(self.temp_dir, "human-decision")
        self.lock_dir = os.path.join(self.temp_dir, "lock")
        os.makedirs(self.prop_dir, exist_ok=True)
        os.makedirs(self.dec_dir, exist_ok=True)
        os.makedirs(self.lock_dir, exist_ok=True)

        # Copy original valid proposal artifacts to working temp
        evidence_prop = os.path.join(self.evidence_dir, "lock-proposal")
        for f in os.listdir(evidence_prop):
            shutil.copyfile(os.path.join(evidence_prop, f), os.path.join(self.prop_dir, f))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # VECTOR 1: selected_gpu substitution
    # Tests substituting 'host', 'lavapipe', 'auto', or 'rogue_mode'
    # -------------------------------------------------------------------------
    def test_vector_1_selected_gpu_substitution_runner_gate(self):
        """Vector 1.1: Runner fails closed on any GPU other than swiftshader."""
        for rogue_gpu in ["host", "lavapipe", "auto", "software", "swangle", "rogue_mode"]:
            sub_dec = copy.deepcopy(self.canonical_decision)
            sub_dec["selected_gpu"] = rogue_gpu
            with self.subTest(rogue_gpu=rogue_gpu):
                with self.assertRaises((ValueError, RuntimeError)) as ctx:
                    run_lock_pipeline(
                        proposal_dir=self.prop_dir,
                        decision_dir=self.dec_dir,
                        lock_dir=self.lock_dir,
                        evaluation_time_utc=CANONICAL_EVAL_TIME,
                        decision_override=sub_dec,
                    )
                # Must fail either in verify_human_decision or in runner explicit gate
                err_msg = str(ctx.exception)
                self.assertTrue(
                    "UNEXPECTED_SELECTED_GPU" in err_msg or "HUMAN_DECISION_VALIDATION_FAILED" in err_msg,
                    f"Unexpected error for GPU {rogue_gpu}: {err_msg}",
                )

    def test_vector_1_selected_gpu_substitution_model_verifier(self):
        """Vector 1.2: Model verify_human_decision rejects candidate not in candidate_modes."""
        sub_dec = copy.deepcopy(self.canonical_decision)
        sub_dec["selected_gpu"] = "rogue_mode"
        is_valid, errors, report = verify_human_decision(
            sub_dec, self.canonical_proposal, CANONICAL_EVAL_TIME
        )
        self.assertFalse(is_valid)
        self.assertFalse(report["SELECTED_GPU_VALID"])
        self.assertTrue(any("not in proposal candidate_modes" in e for e in errors))

        # Also compute_lock_candidate must fail closed
        ok, l_dig, l_pay, errs = compute_lock_candidate(
            self.canonical_proposal, sub_dec, CANONICAL_EVAL_TIME
        )
        self.assertFalse(ok)
        self.assertIsNone(l_dig)

    def test_vector_1_selected_gpu_substitution_digest_isolation(self):
        """Vector 1.3: Any selected_gpu mutation in lock_payload breaks CANONICAL_LOCK_DIGEST."""
        for rogue_gpu in ["host", "lavapipe", "auto", "rogue_mode", "vulkan", "none"]:
            mut_lock = copy.deepcopy(self.canonical_lock)
            mut_lock["selected_gpu"] = rogue_gpu
            mut_digest = hash_canonical_json_v1(mut_lock)
            self.assertNotEqual(
                mut_digest,
                CANONICAL_LOCK_DIGEST,
                f"Digest collision or preservation for rogue_gpu={rogue_gpu}",
            )

    # -------------------------------------------------------------------------
    # VECTOR 2: package revision substitution
    # Tests altering emulator revision or platform revision in hard_locks
    # -------------------------------------------------------------------------
    def test_vector_2_package_revision_substitution_in_proposal(self):
        """Vector 2.1: Tampering emulator or platform revision in proposal breaks catalog_digest invariant."""
        # A. Alter emulator revision
        mut_prop = copy.deepcopy(self.canonical_proposal)
        for pkg in mut_prop["hard_locks"]:
            if pkg["package_path"] == "emulator":
                pkg["revision"] = "38.0.0"

        with self.assertRaises(ValueError) as ctx:
            validate_lock_proposal(mut_prop)
        self.assertIn("catalog_digest", str(ctx.exception))

        # B. Alter platforms;android-36 revision
        mut_prop2 = copy.deepcopy(self.canonical_proposal)
        for pkg in mut_prop2["hard_locks"]:
            if pkg["package_path"] == "platforms;android-36":
                pkg["revision"] = "3"

        with self.assertRaises(ValueError) as ctx:
            validate_lock_proposal(mut_prop2)
        self.assertIn("catalog_digest", str(ctx.exception))

    def test_vector_2_package_revision_substitution_in_lock_payload(self):
        """Vector 2.2: Tampering package revision in lock_payload breaks CANONICAL_LOCK_DIGEST."""
        for pkg_path, new_rev in [
            ("emulator", "38.0.0"),
            ("platforms;android-36", "3"),
            ("build-tools;36.0.0", "36.0.1"),
            ("platform-tools", "38.0.0"),
            ("system-images;android-36;default;x86_64", "3"),
        ]:
            mut_lock = copy.deepcopy(self.canonical_lock)
            for pkg in mut_lock["hard_locks"]:
                if pkg["package_path"] == pkg_path:
                    pkg["revision"] = new_rev

            mut_digest = hash_canonical_json_v1(mut_lock)
            self.assertNotEqual(
                mut_digest,
                CANONICAL_LOCK_DIGEST,
                f"Digest preserved after modifying revision for {pkg_path}",
            )

    # -------------------------------------------------------------------------
    # VECTOR 3: proposal digest substitution
    # Tests tampering with proposal_digest
    # -------------------------------------------------------------------------
    def test_vector_3_proposal_digest_substitution_in_decision(self):
        """Vector 3.1: verify_human_decision rejects tampered proposal_digest."""
        tampered_digests = [
            "0000000000000000000000000000000000000000000000000000000000000000",
            "5517290ec9b90cdcbc13ad34a1228a1ff422f2a5c2326d622e9f2ae249b411b5",  # flipped 1 bit
            "e9148d7bcdb5124182f87787a78899845aa9a60aefbe5c4bc581539201b4f6ed",  # catalog digest instead
        ]
        for bad_digest in tampered_digests:
            sub_dec = copy.deepcopy(self.canonical_decision)
            sub_dec["proposal_digest"] = bad_digest
            is_valid, errors, report = verify_human_decision(
                sub_dec, self.canonical_proposal, CANONICAL_EVAL_TIME
            )
            self.assertFalse(is_valid)
            self.assertFalse(report["REFERENCES_MATCH"])
            self.assertTrue(any("proposal_digest mismatch" in e for e in errors))

            ok, l_dig, l_pay, errs = compute_lock_candidate(
                self.canonical_proposal, sub_dec, CANONICAL_EVAL_TIME
            )
            self.assertFalse(ok)
            self.assertIsNone(l_dig)

    def test_vector_3_proposal_digest_substitution_in_lock_payload(self):
        """Vector 3.2: Tampering proposal_digest in lock_payload breaks CANONICAL_LOCK_DIGEST."""
        mut_lock = copy.deepcopy(self.canonical_lock)
        mut_lock["proposal_digest"] = "1" * 64
        mut_digest = hash_canonical_json_v1(mut_lock)
        self.assertNotEqual(mut_digest, CANONICAL_LOCK_DIGEST)

    # -------------------------------------------------------------------------
    # VECTOR 4: catalog digest substitution
    # Tests tampering with catalog_digest
    # -------------------------------------------------------------------------
    def test_vector_4_catalog_digest_substitution_in_proposal(self):
        """Vector 4.1: Tampering catalog_digest in proposal breaks internal hard_locks check."""
        mut_prop = copy.deepcopy(self.canonical_proposal)
        mut_prop["catalog_digest"] = "2" * 64
        with self.assertRaises(ValueError) as ctx:
            validate_lock_proposal(mut_prop)
        self.assertIn("does not match hard_locks content", str(ctx.exception))

    def test_vector_4_catalog_digest_substitution_in_decision(self):
        """Vector 4.2: verify_human_decision rejects tampered catalog_digest."""
        sub_dec = copy.deepcopy(self.canonical_decision)
        sub_dec["catalog_digest"] = "3" * 64
        is_valid, errors, report = verify_human_decision(
            sub_dec, self.canonical_proposal, CANONICAL_EVAL_TIME
        )
        self.assertFalse(is_valid)
        self.assertFalse(report["REFERENCES_MATCH"])
        self.assertTrue(any("catalog_digest mismatch" in e for e in errors))

    def test_vector_4_catalog_digest_substitution_in_lock_payload(self):
        """Vector 4.3: Tampering catalog_digest in lock_payload breaks CANONICAL_LOCK_DIGEST."""
        mut_lock = copy.deepcopy(self.canonical_lock)
        mut_lock["catalog_digest"] = "4" * 64
        mut_digest = hash_canonical_json_v1(mut_lock)
        self.assertNotEqual(mut_digest, CANONICAL_LOCK_DIGEST)

    # -------------------------------------------------------------------------
    # VECTOR 5: decision tampering
    # Tests altering decision to REJECT or forging review_context/decision_statement
    # -------------------------------------------------------------------------
    def test_vector_5_decision_altering_to_reject(self):
        """Vector 5.1: Altering decision to REJECT prevents lock candidate computation."""
        # REJECT without selected_gpu
        rej_dec = copy.deepcopy(self.canonical_decision)
        rej_dec["decision"] = "REJECT"
        rej_dec["selected_gpu"] = None

        is_valid, errors, report = verify_human_decision(
            rej_dec, self.canonical_proposal, CANONICAL_EVAL_TIME
        )
        self.assertTrue(is_valid)  # Valid as a rejection record

        # But candidate generation must fail closed!
        ok, l_dig, l_pay, errs = compute_lock_candidate(
            self.canonical_proposal, rej_dec, CANONICAL_EVAL_TIME
        )
        self.assertFalse(ok)
        self.assertIsNone(l_dig)
        self.assertIsNone(l_pay)
        self.assertTrue(any("DECISION_IS_NOT_APPROVE" in e for e in errs))

        # REJECT with non-None selected_gpu is invalid schema
        rej_dec_bad = copy.deepcopy(self.canonical_decision)
        rej_dec_bad["decision"] = "REJECT"
        rej_dec_bad["selected_gpu"] = "swiftshader"
        is_valid2, errors2, report2 = verify_human_decision(
            rej_dec_bad, self.canonical_proposal, CANONICAL_EVAL_TIME
        )
        self.assertFalse(is_valid2)
        self.assertTrue(any("selected_gpu must be None or omitted when decision='REJECT'" in e for e in errors2))

    def test_vector_5_decision_altering_to_unrecognized_values(self):
        """Vector 5.2: Altering decision to unauthorized strings fails schema check."""
        for rogue_dec in ["APPROVED", "APPROVE_OVERRIDE", "AUTO_APPROVE", "GRANTED", "", 123]:
            sub_dec = copy.deepcopy(self.canonical_decision)
            sub_dec["decision"] = rogue_dec
            is_valid, errors, report = verify_human_decision(
                sub_dec, self.canonical_proposal, CANONICAL_EVAL_TIME
            )
            self.assertFalse(is_valid)
            self.assertFalse(report["SCHEMA_VALID"])

    def test_vector_5_decision_tampering_review_context(self):
        """Vector 5.3: review_context cannot be missing or empty; forged context breaks artifact integrity."""
        # Missing review_context
        no_ctx = copy.deepcopy(self.canonical_decision)
        del no_ctx["review_context"]
        is_valid, errors, report = verify_human_decision(
            no_ctx, self.canonical_proposal, CANONICAL_EVAL_TIME
        )
        self.assertFalse(is_valid)
        self.assertTrue(any("Missing review_context" in e for e in errors))

        # Empty review_context
        empty_ctx = copy.deepcopy(self.canonical_decision)
        empty_ctx["review_context"] = {}
        is_valid, errors, report = verify_human_decision(
            empty_ctx, self.canonical_proposal, CANONICAL_EVAL_TIME
        )
        self.assertFalse(is_valid)
        self.assertTrue(any("review_context must be a non-empty dictionary" in e for e in errors))

        # Forged review context breaks decision artifact digest
        forged_ctx = copy.deepcopy(self.canonical_decision)
        forged_ctx["review_context"] = {
            "authority_basis": "ROGUE_ADMIN",
            "decision_statement": "Rogue approval bypass.",
        }
        forged_bytes = canonicalize_json_v1(forged_ctx)
        forged_digest = hashlib.sha256(forged_bytes).hexdigest()
        self.assertNotEqual(
            forged_digest,
            CANONICAL_DECISION_DIGEST,
            "Forged review_context preserved decision digest",
        )

    # -------------------------------------------------------------------------
    # VECTOR 6: expired evaluation
    # Tests evaluating at evaluation_time_utc > fresh_until or reviewed_at > evaluation_time_utc
    # -------------------------------------------------------------------------
    def test_vector_6_expired_evaluation_after_fresh_until(self):
        """Vector 6.1: evaluation_time_utc > fresh_until fails closed."""
        # fresh_until is 2026-09-29T13:39:23Z
        expired_eval_times = [
            "2026-09-29T13:39:24Z",  # 1 second after expiration
            "2026-09-30T00:00:00Z",  # next day
            "2027-01-01T00:00:00Z",  # next year
        ]
        for exp_time in expired_eval_times:
            is_valid, errors, report = verify_human_decision(
                self.canonical_decision, self.canonical_proposal, exp_time
            )
            self.assertFalse(is_valid)
            self.assertFalse(report["EVALUATION_TIME_VALID"])
            self.assertFalse(report["FRESHNESS_VALID"])
            self.assertTrue(any("Proposal expired at evaluation time" in e for e in errors))

            ok, l_dig, l_pay, errs = compute_lock_candidate(
                self.canonical_proposal, self.canonical_decision, exp_time
            )
            self.assertFalse(ok)
            self.assertIsNone(l_dig)

    def test_vector_6_temporal_inversion_reviewed_at_greater_than_eval_time(self):
        """Vector 6.2: reviewed_at > evaluation_time_utc (decision in future) fails closed."""
        # reviewed_at is 2026-09-22T14:45:17Z
        future_review_eval_times = [
            "2026-09-22T14:45:16Z",  # 1 second before review
            "2026-09-22T14:00:00Z",  # 45 minutes before review
            "2026-09-22T13:39:23Z",  # exactly at observed_at
        ]
        for early_eval in future_review_eval_times:
            is_valid, errors, report = verify_human_decision(
                self.canonical_decision, self.canonical_proposal, early_eval
            )
            self.assertFalse(is_valid)
            self.assertFalse(report["DECISION_PRECEDES_OR_EQUALS_EVALUATION"])
            self.assertFalse(report["FRESHNESS_VALID"])
            self.assertTrue(any("Decision in future" in e for e in errors))

            ok, l_dig, l_pay, errs = compute_lock_candidate(
                self.canonical_proposal, self.canonical_decision, early_eval
            )
            self.assertFalse(ok)
            self.assertIsNone(l_dig)

    def test_vector_6_reviewed_at_predates_observed_at_or_exceeds_fresh_until(self):
        """Vector 6.3: reviewed_at before observed_at or after fresh_until fails closed."""
        # reviewed_at < observed_at (observed_at: 2026-09-22T13:39:23Z)
        early_dec = copy.deepcopy(self.canonical_decision)
        early_dec["reviewed_at"] = "2026-09-22T13:30:00Z"
        is_valid, errors, report = verify_human_decision(
            early_dec, self.canonical_proposal, CANONICAL_EVAL_TIME
        )
        self.assertFalse(is_valid)
        self.assertFalse(report["REVIEW_TIME_VALID"])
        self.assertTrue(any("Review predates observation" in e for e in errors))

        # reviewed_at > fresh_until (fresh_until: 2026-09-29T13:39:23Z)
        late_dec = copy.deepcopy(self.canonical_decision)
        late_dec["reviewed_at"] = "2026-09-29T14:00:00Z"
        is_valid2, errors2, report2 = verify_human_decision(
            late_dec, self.canonical_proposal, "2026-09-29T14:30:00Z"
        )
        self.assertFalse(is_valid2)
        self.assertFalse(report2["REVIEW_TIME_VALID"])
        self.assertTrue(any("Proposal expired at review time" in e for e in errors2))

    # -------------------------------------------------------------------------
    # VECTOR 7: extra package in hard_locks
    # Tests injecting a 6th package into hard_locks
    # -------------------------------------------------------------------------
    def test_vector_7_extra_package_in_proposal(self):
        """Vector 7.1: Injecting 6th package into proposal hard_locks fails closed."""
        mut_prop = copy.deepcopy(self.canonical_proposal)
        mut_prop["hard_locks"].append({
            "package_path": "ndk;27.0.12077973",
            "revision": "27.0.12077973",
        })
        with self.assertRaises(ValueError) as ctx:
            validate_lock_proposal(mut_prop)
        self.assertIn("must be a list of exactly 5 entries", str(ctx.exception))

    def test_vector_7_extra_package_in_lock_payload(self):
        """Vector 7.2: Injecting 6th package into lock_payload alters digest."""
        mut_lock = copy.deepcopy(self.canonical_lock)
        mut_lock["hard_locks"].append({
            "package_path": "ndk;27.0.12077973",
            "revision": "27.0.12077973",
        })
        mut_digest = hash_canonical_json_v1(mut_lock)
        self.assertNotEqual(mut_digest, CANONICAL_LOCK_DIGEST)

    # -------------------------------------------------------------------------
    # VECTOR 8: missing package in hard_locks
    # Tests removing one of the 5 required packages
    # -------------------------------------------------------------------------
    def test_vector_8_missing_package_in_proposal(self):
        """Vector 8.1: Removing any required package from proposal hard_locks fails closed."""
        for remove_idx in range(5):
            mut_prop = copy.deepcopy(self.canonical_proposal)
            removed = mut_prop["hard_locks"].pop(remove_idx)
            with self.subTest(removed=removed["package_path"]):
                with self.assertRaises(ValueError) as ctx:
                    validate_lock_proposal(mut_prop)
                self.assertIn("must be a list of exactly 5 entries", str(ctx.exception))

    def test_vector_8_missing_package_in_lock_payload(self):
        """Vector 8.2: Removing any package from lock_payload alters digest."""
        for remove_idx in range(5):
            mut_lock = copy.deepcopy(self.canonical_lock)
            removed = mut_lock["hard_locks"].pop(remove_idx)
            mut_digest = hash_canonical_json_v1(mut_lock)
            self.assertNotEqual(
                mut_digest,
                CANONICAL_LOCK_DIGEST,
                f"Digest preserved after removing {removed['package_path']}",
            )

    # -------------------------------------------------------------------------
    # VECTOR 9: environment drift
    # Tests altering jdk_major or emulator_revision in environment_locks
    # -------------------------------------------------------------------------
    def test_vector_9_environment_drift_in_proposal(self):
        """Vector 9.1: Altering jdk_major or emulator_revision in proposal fails closed."""
        # A. Alter jdk_major (must be 17)
        for bad_jdk in [8, 11, 21, 23, "17"]:
            mut_prop = copy.deepcopy(self.canonical_proposal)
            mut_prop["environment"]["jdk_major"] = bad_jdk
            with self.subTest(bad_jdk=bad_jdk):
                with self.assertRaises((ValueError, TypeError)) as ctx:
                    validate_lock_proposal(mut_prop)
                self.assertIn("jdk_major must be integer 17", str(ctx.exception))

        # B. Alter emulator_revision in environment (mismatch with hard_locks)
        mut_prop2 = copy.deepcopy(self.canonical_proposal)
        mut_prop2["environment"]["emulator_revision"] = "38.0.0"
        with self.assertRaises(ValueError) as ctx:
            validate_lock_proposal(mut_prop2)
        self.assertIn("environment.emulator_revision", str(ctx.exception))

    def test_vector_9_environment_drift_in_lock_payload(self):
        """Vector 9.2: Altering environment_locks in lock_payload alters digest."""
        # Alter jdk_major
        mut_lock = copy.deepcopy(self.canonical_lock)
        mut_lock["environment_locks"]["jdk_major"] = 21
        mut_digest = hash_canonical_json_v1(mut_lock)
        self.assertNotEqual(mut_digest, CANONICAL_LOCK_DIGEST)

        # Alter emulator_revision
        mut_lock2 = copy.deepcopy(self.canonical_lock)
        mut_lock2["environment_locks"]["emulator_revision"] = "38.0.0"
        mut_digest2 = hash_canonical_json_v1(mut_lock2)
        self.assertNotEqual(mut_digest2, CANONICAL_LOCK_DIGEST)

    # -------------------------------------------------------------------------
    # INTEGRITY SUMMARY ASSERTIONS
    # -------------------------------------------------------------------------
    def test_summary_three_distinct_digests(self):
        """Verify catalog, proposal, and lock digests are pairwise distinct."""
        self.assertNotEqual(CANONICAL_CATALOG_DIGEST, CANONICAL_PROPOSAL_DIGEST)
        self.assertNotEqual(CANONICAL_PROPOSAL_DIGEST, CANONICAL_LOCK_DIGEST)
        self.assertNotEqual(CANONICAL_CATALOG_DIGEST, CANONICAL_LOCK_DIGEST)

    def test_summary_lock_digest_is_strictly_canonical(self):
        """Verify the exact canonical LOCK_DIGEST is reproduced and immutable."""
        is_valid, l_digest, l_payload, errors = compute_lock_candidate(
            proposal=self.canonical_proposal,
            human_decision=self.canonical_decision,
            evaluation_time_utc=CANONICAL_EVAL_TIME,
        )
        self.assertTrue(is_valid, f"Canonical candidate failed: {errors}")
        self.assertEqual(l_digest, CANONICAL_LOCK_DIGEST)
        self.assertEqual(l_payload, self.canonical_lock)


if __name__ == "__main__":
    unittest.main()
