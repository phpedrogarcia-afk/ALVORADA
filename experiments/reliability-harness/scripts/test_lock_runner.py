#!/usr/bin/env python3
"""
ALVORADA — Unit Test Suite for Lock Runner
Campaign: ALVORADA G1 POST-FOUNDER-APPROVAL EXECUTION CAMPAIGN 001
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
    CONTRACT_HUMAN_DECISION,
    CONTRACT_LOCK_PAYLOAD,
    compute_lock_proposal_digest,
)
from lock_runner import (
    EXTERNAL_FOUNDER_DECISION,
    materialize_human_decision,
    materialize_lock_payload,
    run_lock_pipeline,
)
from proposal_assembly_runner import verify_directory_checksums


class TestLockRunner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.prop_dir = os.path.join(self.temp_dir, "lock-proposal")
        self.dec_dir = os.path.join(self.temp_dir, "human-decision")
        self.lock_dir = os.path.join(self.temp_dir, "lock")
        os.makedirs(self.prop_dir, exist_ok=True)

        # Copy existing verified proposal from evidence or generate test proposal
        evidence_prop_dir = os.path.join(
            os.path.dirname(SCRIPTS_DIR),
            "evidence",
            "lock-proposal",
        )
        if os.path.isdir(evidence_prop_dir):
            for fname in os.listdir(evidence_prop_dir):
                shutil.copyfile(
                    os.path.join(evidence_prop_dir, fname),
                    os.path.join(self.prop_dir, fname),
                )
        else:
            raise FileNotFoundError("Missing evidence lock-proposal directory")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_materialize_human_decision(self):
        decision, dec_digest = materialize_human_decision(self.dec_dir)
        self.assertEqual(dec_digest, "5d240bb22205000c5e805fba1c45a99b015e412bebadeb508f88236de74bc5b7")
        verify_directory_checksums(self.dec_dir, required=True)

        txt_file = os.path.join(self.dec_dir, "human-lock-decision.txt")
        with open(txt_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("SOURCE_OF_AUTHORITY = EXTERNAL_FOUNDER_DECISION", content)
        self.assertIn("AGENT_DID_NOT_SELECT_GPU = TRUE", content)
        self.assertIn("swiftshader", content)

    def test_run_lock_pipeline_happy_path(self):
        eval_time = "2026-09-22T14:48:00Z"
        decision, dec_digest, lock_payload, lock_digest = run_lock_pipeline(
            proposal_dir=self.prop_dir,
            decision_dir=self.dec_dir,
            lock_dir=self.lock_dir,
            evaluation_time_utc=eval_time,
        )

        self.assertEqual(dec_digest, "5d240bb22205000c5e805fba1c45a99b015e412bebadeb508f88236de74bc5b7")
        self.assertEqual(lock_digest, "ac243a03caca0333eec85721cbd27f828a001c3b19ed80d7994e33589f065f05")
        self.assertEqual(lock_payload["selected_gpu"], "swiftshader")
        self.assertEqual(lock_payload["contract"], CONTRACT_LOCK_PAYLOAD)
        self.assertEqual(len(lock_payload["hard_locks"]), 5)

        verify_directory_checksums(self.lock_dir, required=True)
        txt_path = os.path.join(self.lock_dir, "lock.txt")
        with open(txt_path, "r", encoding="utf-8") as f:
            txt_content = f.read()
        self.assertIn("CLASSIFICATION: APPROVED_EXPERIMENTAL_G1_LOCK", txt_content)
        self.assertIn("ac243a03caca0333eec85721cbd27f828a001c3b19ed80d7994e33589f065f05", txt_content)

    def test_run_lock_pipeline_fails_on_tampered_proposal_checksum(self):
        prop_file = os.path.join(self.prop_dir, "lock-proposal.json")
        with open(prop_file, "wb") as f:
            f.write(b"tampered")

        with self.assertRaises(ValueError) as ctx:
            run_lock_pipeline(
                proposal_dir=self.prop_dir,
                decision_dir=self.dec_dir,
                lock_dir=self.lock_dir,
                evaluation_time_utc="2026-09-22T14:48:00Z",
            )
        self.assertIn("CHECKSUM_MISMATCH", str(ctx.exception))

    def test_run_lock_pipeline_fails_on_rejected_decision(self):
        bad_dec = dict(EXTERNAL_FOUNDER_DECISION)
        bad_dec["decision"] = "REJECT"
        bad_dec["selected_gpu"] = None

        with self.assertRaises(ValueError):
            run_lock_pipeline(
                proposal_dir=self.prop_dir,
                decision_dir=self.dec_dir,
                lock_dir=self.lock_dir,
                evaluation_time_utc="2026-09-22T14:48:00Z",
                decision_override=bad_dec,
            )

    def test_run_lock_pipeline_fails_on_rogue_gpu(self):
        bad_dec = dict(EXTERNAL_FOUNDER_DECISION)
        bad_dec["selected_gpu"] = "host"  # Not swiftshader as approved

        with self.assertRaises(ValueError) as ctx:
            run_lock_pipeline(
                proposal_dir=self.prop_dir,
                decision_dir=self.dec_dir,
                lock_dir=self.lock_dir,
                evaluation_time_utc="2026-09-22T14:48:00Z",
                decision_override=bad_dec,
            )
        self.assertIn("UNEXPECTED_SELECTED_GPU", str(ctx.exception))

    def test_run_lock_pipeline_fails_on_temporal_inversion(self):
        # eval_time earlier than reviewed_at
        early_eval = "2026-09-22T14:40:00Z"
        with self.assertRaises(ValueError) as ctx:
            run_lock_pipeline(
                proposal_dir=self.prop_dir,
                decision_dir=self.dec_dir,
                lock_dir=self.lock_dir,
                evaluation_time_utc=early_eval,
            )
        self.assertIn("HUMAN_DECISION_VALIDATION_FAILED", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
