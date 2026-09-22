from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import random
import tempfile
from typing import Any, Dict, List, Optional
import unittest

from e1_scenario_runner import CONTRACT_E1_EVIDENCE, APPROVED_LOCK_DIGEST


class StateMachineSimulator:
    """Pure-logic simulator of the Wake Core Android adapter state machine for adversarial testing."""
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.alarm_id = ""
        self.generation = 0
        self.occurrence_id = ""
        self.parent_occurrence_id = ""
        self.state = "IDLE"
        self.duplicate_count = 0
        self.stale_rejection_count = 0
        self.reconciliation_count = 0
        self.audio_sessions_started = 0
        self.software_audio_started = False
        self.audible_claimed = False
        self.human_awake_claimed = False

    def configure(self, alarm_id: str, generation: int) -> str:
        if generation < 1:
            return "ERROR_INVALID_GENERATION"
        self.alarm_id = alarm_id
        self.generation = generation
        self.state = "CONFIGURED"
        return "OK"

    def arm(self, occurrence_id: str, generation: int) -> str:
        if self.state not in ("CONFIGURED", "IDLE", "SNOOZED", "DISMISSED"):
            return f"INVALID_TRANSITION_FROM_{self.state}"
        if generation < self.generation:
            return "STALE_GENERATION"
        self.occurrence_id = occurrence_id
        self.generation = generation
        self.state = "ARMED"
        return "OK"

    def trigger(self, occurrence_id: str, generation: int) -> str:
        # 1. Stale generation check
        if generation < self.generation:
            self.stale_rejection_count += 1
            return "STALE_GENERATION_REJECTED"

        # 2. Duplicate / terminal check
        if occurrence_id == self.parent_occurrence_id:
            self.duplicate_count += 1
            return "DUPLICATE_TRIGGER_REJECTED"

        if occurrence_id == self.occurrence_id and self.state in (
            "TRIGGERED", "SOFTWARE_AUDIO_STARTED", "DISMISSED", "RECOVERED_LATE"
        ):
            self.duplicate_count += 1
            return "DUPLICATE_TRIGGER_REJECTED"

        # 3. Only ARMED or SNOOZED can trigger legitimately
        if self.state not in ("ARMED", "SNOOZED"):
            return f"INVALID_TRIGGER_FROM_{self.state}"

        self.state = "TRIGGERED"
        # Enter software audio
        self.software_audio_started = True
        self.audio_sessions_started += 1
        self.state = "SOFTWARE_AUDIO_STARTED"
        return "TRIGGER_ACCEPTED"

    def snooze(self, child_occurrence_id: str) -> str:
        if self.state not in ("TRIGGERED", "SOFTWARE_AUDIO_STARTED"):
            return f"CANNOT_SNOOZE_FROM_{self.state}"
        self.parent_occurrence_id = self.occurrence_id
        self.occurrence_id = child_occurrence_id
        self.state = "SNOOZED"
        return "SNOOZED_OK"

    def dismiss(self) -> str:
        if self.state not in ("ARMED", "TRIGGERED", "SOFTWARE_AUDIO_STARTED", "SNOOZED"):
            return f"CANNOT_DISMISS_FROM_{self.state}"
        self.state = "DISMISSED"
        return "DISMISSED_OK"

    def reconcile(self, target_epoch_ms: int, now_epoch_ms: int) -> str:
        self.reconciliation_count += 1
        if self.state != "ARMED":
            return "NOOP_NOT_ARMED"

        if target_epoch_ms > now_epoch_ms:
            return "RESCHEDULED_FUTURE"

        overdue_ms = now_epoch_ms - target_epoch_ms
        if overdue_ms <= 600_000: # 10 min
            self.state = "RECOVERED_LATE"
            self.software_audio_started = True
            self.audio_sessions_started += 1
            return "RECOVERED_LATE"
        else:
            self.state = "OUTCOME_UNKNOWN"
            return "SUPPRESSED_OVERDUE_PAST_LIMIT"


class TestReliabilityRedTeam(unittest.TestCase):
    def setUp(self) -> None:
        self.sm = StateMachineSimulator()

    # =========================================================================
    # ROLE 1: STATE_MACHINE_RED_TEAM
    # =========================================================================
    def test_red_team_duplicate_trigger_suppression(self) -> None:
        """Adversarial attempt to trigger multiple audio sessions from the same occurrence."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("occ_1", 1)
        res1 = self.sm.trigger("occ_1", 1)
        self.assertEqual(res1, "TRIGGER_ACCEPTED")
        self.assertEqual(self.sm.audio_sessions_started, 1)

        # Replay attack: 50 duplicate injections
        for _ in range(50):
            res_dup = self.sm.trigger("occ_1", 1)
            self.assertEqual(res_dup, "DUPLICATE_TRIGGER_REJECTED")

        # Invariant: exactly 1 audio session was started, 50 duplicates recorded
        self.assertEqual(self.sm.audio_sessions_started, 1)
        self.assertEqual(self.sm.duplicate_count, 50)

    def test_red_team_stale_generation_injection(self) -> None:
        """Adversarial attempt to trigger using an obsolete/stale generation."""
        self.sm.configure("alarm_1", generation=1)
        # Advance generation to 5
        self.sm.configure("alarm_1", generation=5)
        self.sm.arm("occ_current", 5)

        # Inject stale callbacks from gen 1, 2, 3, 4
        for stale_gen in (1, 2, 3, 4):
            res = self.sm.trigger(f"occ_stale_{stale_gen}", stale_gen)
            self.assertEqual(res, "STALE_GENERATION_REJECTED")

        self.assertEqual(self.sm.stale_rejection_count, 4)
        self.assertEqual(self.sm.state, "ARMED") # active state uncorrupted
        self.assertEqual(self.sm.audio_sessions_started, 0)

    def test_red_team_resurrection_after_dismiss(self) -> None:
        """Adversarial attempt to resurrect an alarm after user dismissal."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("occ_dismiss_target", 1)
        self.sm.trigger("occ_dismiss_target", 1)
        self.sm.dismiss()
        self.assertEqual(self.sm.state, "DISMISSED")

        # Attempt to re-trigger the dismissed occurrence
        res = self.sm.trigger("occ_dismiss_target", 1)
        self.assertEqual(res, "DUPLICATE_TRIGGER_REJECTED")
        self.assertEqual(self.sm.audio_sessions_started, 1)

    def test_red_team_snooze_duplication_and_state_guards(self) -> None:
        """Adversarial attempt to snooze un-triggered or already-snoozed states."""
        # Cannot snooze IDLE
        self.assertIn("CANNOT_SNOOZE", self.sm.snooze("child_0"))
        # Cannot snooze CONFIGURED
        self.sm.configure("alarm_1", 1)
        self.assertIn("CANNOT_SNOOZE", self.sm.snooze("child_0"))
        # Cannot snooze ARMED
        self.sm.arm("occ_1", 1)
        self.assertIn("CANNOT_SNOOZE", self.sm.snooze("child_0"))

        # Trigger and snooze once
        self.sm.trigger("occ_1", 1)
        self.assertEqual(self.sm.snooze("child_1"), "SNOOZED_OK")
        self.assertEqual(self.sm.state, "SNOOZED")

        # Cannot snooze again while in SNOOZED
        self.assertIn("CANNOT_SNOOZE", self.sm.snooze("child_2"))

        # Trigger child occurrence
        res_child = self.sm.trigger("child_1", 1)
        self.assertEqual(res_child, "TRIGGER_ACCEPTED")
        self.assertEqual(self.sm.state, "SOFTWARE_AUDIO_STARTED")
        self.assertEqual(self.sm.audio_sessions_started, 2)

        # Duplicate trigger of child occurrence
        res_dup_child = self.sm.trigger("child_1", 1)
        self.assertEqual(res_dup_child, "DUPLICATE_TRIGGER_REJECTED")
        self.assertEqual(self.sm.duplicate_count, 1)

        # Duplicate trigger of parent occurrence
        res_dup_parent = self.sm.trigger("occ_1", 1)
        self.assertEqual(res_dup_parent, "DUPLICATE_TRIGGER_REJECTED")
        self.assertEqual(self.sm.duplicate_count, 2)

    # =========================================================================
    # ROLE 2: ANDROID_LIFECYCLE_RED_TEAM
    # =========================================================================
    def test_red_team_repeated_reconciliation_stress(self) -> None:
        """Adversarial attempt to flood reconciliation and cause drift or duplicate occurrences."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("occ_future", 1)

        now = 1000000
        target = now + 50000 # 50s future

        # Flood 100 reconciliations
        for _ in range(100):
            res = self.sm.reconcile(target_epoch_ms=target, now_epoch_ms=now)
            self.assertEqual(res, "RESCHEDULED_FUTURE")

        self.assertEqual(self.sm.reconciliation_count, 100)
        self.assertEqual(self.sm.state, "ARMED")
        self.assertEqual(self.sm.audio_sessions_started, 0)
        self.assertEqual(self.sm.duplicate_count, 0)

    def test_red_team_late_recovery_boundary_cliff(self) -> None:
        """Test strict boundary cliff at exactly 10 minutes (600,000 ms)."""
        now = 2000000
        limit_ms = 600_000

        # At exactly 10 minutes overdue: RECOVERED_LATE
        self.sm.reset()
        self.sm.configure("alarm_1", 1)
        self.sm.arm("occ_boundary_in", 1)
        res_in = self.sm.reconcile(target_epoch_ms=now - limit_ms, now_epoch_ms=now)
        self.assertEqual(res_in, "RECOVERED_LATE")
        self.assertEqual(self.sm.state, "RECOVERED_LATE")

        # At 10 minutes + 1 ms overdue: NO SURPRISE ALARM -> OUTCOME_UNKNOWN
        self.sm.reset()
        self.sm.configure("alarm_1", 1)
        self.sm.arm("occ_boundary_out", 1)
        res_out = self.sm.reconcile(target_epoch_ms=now - (limit_ms + 1), now_epoch_ms=now)
        self.assertEqual(res_out, "SUPPRESSED_OVERDUE_PAST_LIMIT")
        self.assertEqual(self.sm.state, "OUTCOME_UNKNOWN")

    # =========================================================================
    # ROLE 3: EVIDENCE_RED_TEAM
    # =========================================================================
    def test_red_team_audible_claim_falsification(self) -> None:
        """Audit verifier that detects and rejects any illegal claim of AUDIBLE or HUMAN_AWAKE."""
        def audit_report(report_dict: Dict[str, Any]) -> Tuple[bool, str]:
            if report_dict.get("audible_claimed") is True:
                return False, "EPISTEMIC_VIOLATION: audible_claimed cannot be True in emulator"
            if report_dict.get("human_awake_claimed") is True:
                return False, "EPISTEMIC_VIOLATION: human_awake_claimed cannot be True in emulator"
            if report_dict.get("statistical_summary", {}).get("duplicate_triggers_accepted", 0) > 0:
                return False, "RELIABILITY_VIOLATION: duplicate triggers accepted > 0"
            return True, "AUDIT_PASS"

        # Compliant report
        valid_report = {
            "contract": CONTRACT_E1_EVIDENCE,
            "audible_claimed": False,
            "human_awake_claimed": False,
            "statistical_summary": {"duplicate_triggers_accepted": 0},
        }
        ok, msg = audit_report(valid_report)
        self.assertTrue(ok)

        # Illegal audible claim
        tampered_report = copy.deepcopy(valid_report)
        tampered_report["audible_claimed"] = True
        ok, msg = audit_report(tampered_report)
        self.assertFalse(ok)
        self.assertIn("EPISTEMIC_VIOLATION", msg)

        # Illegal duplicate accepted
        dup_report = copy.deepcopy(valid_report)
        dup_report["statistical_summary"]["duplicate_triggers_accepted"] = 1
        ok, msg = audit_report(dup_report)
        self.assertFalse(ok)
        self.assertIn("RELIABILITY_VIOLATION", msg)

    # =========================================================================
    # PHASE 16: MUTATION / FUZZING
    # =========================================================================
    def test_mutation_fuzz_state_machine_random_actions(self) -> None:
        """Apply 500 randomized mutations/fuzz actions and assert invariants hold."""
        rng = random.Random(42) # Deterministic seed

        valid_states = {
            "IDLE", "CONFIGURED", "ARMED", "TRIGGERED", "SOFTWARE_AUDIO_STARTED",
            "SNOOZED", "DISMISSED", "RECOVERED_LATE", "OUTCOME_UNKNOWN"
        }

        for iteration in range(500):
            action = rng.choice(["configure", "arm", "trigger", "snooze", "dismiss", "reconcile", "reset"])
            occ_id = f"occ_{rng.randint(1, 5)}"
            gen = rng.randint(0, 4)

            if action == "configure":
                self.sm.configure(f"alarm_{rng.randint(1, 3)}", gen)
            elif action == "arm":
                self.sm.arm(occ_id, gen)
            elif action == "trigger":
                self.sm.trigger(occ_id, gen)
            elif action == "snooze":
                self.sm.snooze(f"child_{rng.randint(1, 5)}")
            elif action == "dismiss":
                self.sm.dismiss()
            elif action == "reconcile":
                target = rng.randint(500_000, 1_500_000)
                now = 1_000_000
                self.sm.reconcile(target, now)
            elif action == "reset":
                self.sm.reset()

            # Global Invariants:
            self.assertIn(self.sm.state, valid_states, f"Iteration {iteration}: state corrupted to {self.sm.state}")
            self.assertFalse(self.sm.audible_claimed, "Audible was claimed during fuzzing")
            self.assertFalse(self.sm.human_awake_claimed, "Human awake was claimed during fuzzing")


if __name__ == "__main__":
    unittest.main()
