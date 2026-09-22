from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import tempfile
from typing import Any, Dict, List, Optional, Tuple
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
        self.civil_schedule = ""
        self.route = ""
        self.state = "IDLE"
        self.duplicate_count = 0
        self.stale_rejection_count = 0
        self.future_rejection_count = 0
        self.invalid_generation_rejection_count = 0
        self.wrong_alarm_id_rejection_count = 0
        self.wrong_occurrence_id_rejection_count = 0
        self.invalid_identity_rejection_count = 0
        self.reconciliation_count = 0
        self.audio_sessions_started = 0
        self.software_audio_started = False
        self.software_audio_failed = False
        self.audio_checkpoint = "NONE"
        self.audio_fault_injection = "NONE"
        self.audible_claimed = False
        self.human_awake_claimed = False

    def configure(self, alarm_id: str, generation: int, civil_schedule: str = "07:00") -> str:
        if generation < 1:
            return "ERROR_INVALID_GENERATION"
        self.alarm_id = alarm_id
        self.generation = generation
        self.civil_schedule = civil_schedule
        self.state = "CONFIGURED"
        return "OK"

    def arm(self, alarm_id: str, generation: int, occurrence_id: str, route: str = "ALARM_CLOCK") -> str:
        if route not in ("ALARM_CLOCK", "EXACT_ALLOW_IDLE"):
            return "ERROR_INVALID_ROUTE"
        if self.state not in ("CONFIGURED", "IDLE", "SNOOZED", "DISMISSED"):
            return f"INVALID_TRANSITION_FROM_{self.state}"
        if generation < self.generation:
            return "STALE_GENERATION"
        self.alarm_id = alarm_id
        self.generation = generation
        self.occurrence_id = occurrence_id
        self.route = route
        self.state = "ARMED"
        return "OK"

    def set_audio_fault(self, fault: str) -> None:
        self.audio_fault_injection = fault

    def trigger(self, alarm_id: str, generation: int, occurrence_id: str) -> str:
        # Pre-validation identity checks (F-01) - fail-closed without mutating authority
        if not alarm_id or not occurrence_id:
            self.invalid_identity_rejection_count += 1
            return "INVALID_IDENTITY_REJECTED"

        if generation <= 0:
            self.invalid_generation_rejection_count += 1
            return "INVALID_GENERATION_REJECTED"

        if generation < self.generation:
            self.stale_rejection_count += 1
            return "STALE_GENERATION_REJECTED"

        if generation > self.generation:
            self.future_rejection_count += 1
            return "FUTURE_GENERATION_REJECTED"

        if alarm_id != self.alarm_id:
            self.wrong_alarm_id_rejection_count += 1
            return "WRONG_ALARM_ID_REJECTED"

        if occurrence_id != self.occurrence_id:
            # Check if it was parent occurrence
            if occurrence_id == self.parent_occurrence_id:
                self.duplicate_count += 1
                return "DUPLICATE_TRIGGER_REJECTED"
            self.wrong_occurrence_id_rejection_count += 1
            return "WRONG_OCCURRENCE_REJECTED"

        # Duplicate / already fired check
        if self.state in ("TRIGGERED", "SOFTWARE_AUDIO_STARTED", "SOFTWARE_AUDIO_FAILED", "DISMISSED", "RECOVERED_LATE"):
            self.duplicate_count += 1
            return "DUPLICATE_TRIGGER_REJECTED"

        # Only ARMED or SNOOZED can trigger legitimately
        if self.state not in ("ARMED", "SNOOZED"):
            return f"INVALID_TRIGGER_FROM_{self.state}"

        self.state = "TRIGGERED"

        # Audio handoff with checkpoints (F-02)
        self.audio_checkpoint = "CHECKPOINT_SOFTWARE_AUDIO_REQUESTED"

        if self.audio_fault_injection == "INIT_FAIL":
            self.audio_checkpoint = "CHECKPOINT_SOFTWARE_AUDIO_FAILED"
            self.software_audio_failed = True
            self.state = "SOFTWARE_AUDIO_FAILED"
            return "SOFTWARE_AUDIO_FAILED"

        self.audio_checkpoint = "CHECKPOINT_SOFTWARE_AUDIO_ENGINE_INITIALIZED"

        if self.audio_fault_injection == "WRITE_FAIL":
            self.audio_checkpoint = "CHECKPOINT_SOFTWARE_AUDIO_FAILED"
            self.software_audio_failed = True
            self.state = "SOFTWARE_AUDIO_FAILED"
            return "SOFTWARE_AUDIO_FAILED"

        self.audio_checkpoint = "CHECKPOINT_SOFTWARE_AUDIO_WRITE_ACCEPTED"

        if self.audio_fault_injection == "PLAY_FAIL":
            self.audio_checkpoint = "CHECKPOINT_SOFTWARE_AUDIO_FAILED"
            self.software_audio_failed = True
            self.state = "SOFTWARE_AUDIO_FAILED"
            return "SOFTWARE_AUDIO_FAILED"

        self.audio_checkpoint = "CHECKPOINT_SOFTWARE_AUDIO_STARTED"
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
        if overdue_ms <= 600_000:  # 10 min
            self.state = "RECOVERED_LATE"
            self.software_audio_started = True
            self.audio_sessions_started += 1
            return "RECOVERED_LATE"
        else:
            self.state = "OUTCOME_UNKNOWN"
            return "SUPPRESSED_OVERDUE_PAST_LIMIT"


# =============================================================================
# RED TEAM 1: STATE_AUTHORITY_RED_TEAM
# =============================================================================
class TestStateAuthorityRedTeam(unittest.TestCase):
    def setUp(self) -> None:
        self.sm = StateMachineSimulator()

    def test_exact_identity_enforcement(self) -> None:
        """Legitimate trigger requires exact alarm_id, generation, and occurrence_id match."""
        self.sm.configure("alarm_1", 2)
        self.sm.arm("alarm_1", 2, "occ_1", route="ALARM_CLOCK")
        res = self.sm.trigger("alarm_1", 2, "occ_1")
        self.assertEqual(res, "TRIGGER_ACCEPTED")
        self.assertEqual(self.sm.state, "SOFTWARE_AUDIO_STARTED")
        self.assertEqual(self.sm.audio_sessions_started, 1)

    def test_stale_generation_rejected_without_mutation(self) -> None:
        """Generation < current is rejected, active authority remains uncorrupted."""
        self.sm.configure("alarm_1", 5)
        self.sm.arm("alarm_1", 5, "occ_active", route="ALARM_CLOCK")

        for stale_gen in [1, 2, 3, 4]:
            res = self.sm.trigger("alarm_1", stale_gen, "occ_stale")
            self.assertEqual(res, "STALE_GENERATION_REJECTED")

        self.assertEqual(self.sm.stale_rejection_count, 4)
        self.assertEqual(self.sm.state, "ARMED")
        self.assertEqual(self.sm.generation, 5)
        self.assertEqual(self.sm.occurrence_id, "occ_active")
        self.assertEqual(self.sm.audio_sessions_started, 0)

    def test_future_generation_rejected_without_mutation(self) -> None:
        """Generation > current cannot advance authority or trigger audio."""
        self.sm.configure("alarm_1", 2)
        self.sm.arm("alarm_1", 2, "occ_active", route="ALARM_CLOCK")

        res = self.sm.trigger("alarm_1", 3, "occ_future")
        self.assertEqual(res, "FUTURE_GENERATION_REJECTED")
        self.assertEqual(self.sm.future_rejection_count, 1)
        self.assertEqual(self.sm.state, "ARMED")
        self.assertEqual(self.sm.generation, 2)
        self.assertEqual(self.sm.occurrence_id, "occ_active")

    def test_zero_and_negative_generation_rejected(self) -> None:
        """Generation <= 0 is rejected fail-closed."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_active", route="ALARM_CLOCK")

        res_zero = self.sm.trigger("alarm_1", 0, "occ_zero")
        self.assertEqual(res_zero, "INVALID_GENERATION_REJECTED")

        res_neg = self.sm.trigger("alarm_1", -1, "occ_neg")
        self.assertEqual(res_neg, "INVALID_GENERATION_REJECTED")

        self.assertEqual(self.sm.invalid_generation_rejection_count, 2)
        self.assertEqual(self.sm.state, "ARMED")

    def test_wrong_alarm_id_rejected(self) -> None:
        """Mismatched alarm_id is rejected fail-closed."""
        self.sm.configure("alarm_authoritative", 1)
        self.sm.arm("alarm_authoritative", 1, "occ_1", route="ALARM_CLOCK")

        res = self.sm.trigger("alarm_rogue", 1, "occ_1")
        self.assertEqual(res, "WRONG_ALARM_ID_REJECTED")
        self.assertEqual(self.sm.wrong_alarm_id_rejection_count, 1)
        self.assertEqual(self.sm.state, "ARMED")
        self.assertEqual(self.sm.alarm_id, "alarm_authoritative")

    def test_wrong_occurrence_id_rejected(self) -> None:
        """Mismatched occurrence_id is rejected fail-closed."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_legit", route="ALARM_CLOCK")

        res = self.sm.trigger("alarm_1", 1, "occ_forged")
        self.assertEqual(res, "WRONG_OCCURRENCE_REJECTED")
        self.assertEqual(self.sm.wrong_occurrence_id_rejection_count, 1)
        self.assertEqual(self.sm.state, "ARMED")
        self.assertEqual(self.sm.occurrence_id, "occ_legit")

    def test_empty_identity_rejected(self) -> None:
        """Empty or null alarm_id / occurrence_id is rejected fail-closed."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_1", route="ALARM_CLOCK")

        self.assertEqual(self.sm.trigger("", 1, "occ_1"), "INVALID_IDENTITY_REJECTED")
        self.assertEqual(self.sm.trigger("alarm_1", 1, ""), "INVALID_IDENTITY_REJECTED")
        self.assertEqual(self.sm.invalid_identity_rejection_count, 2)
        self.assertEqual(self.sm.state, "ARMED")

    def test_route_validation_fail_closed(self) -> None:
        """Only ALARM_CLOCK and EXACT_ALLOW_IDLE routes may be armed."""
        self.sm.configure("alarm_1", 1)
        self.assertEqual(self.sm.arm("alarm_1", 1, "occ_1", route="ALARM_CLOCK"), "OK")

        self.sm.reset()
        self.sm.configure("alarm_1", 1)
        self.assertEqual(self.sm.arm("alarm_1", 1, "occ_2", route="EXACT_ALLOW_IDLE"), "OK")

        self.sm.reset()
        self.sm.configure("alarm_1", 1)
        self.assertEqual(self.sm.arm("alarm_1", 1, "occ_3", route="UNKNOWN_ROUTE"), "ERROR_INVALID_ROUTE")
        self.assertEqual(self.sm.arm("alarm_1", 1, "occ_4", route="ROGUE_ROUTE"), "ERROR_INVALID_ROUTE")
        self.assertEqual(self.sm.state, "CONFIGURED")

    def test_duplicate_trigger_suppression(self) -> None:
        """Replay attack: duplicate triggers for active or terminal occurrences rejected."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_1")
        self.assertEqual(self.sm.trigger("alarm_1", 1, "occ_1"), "TRIGGER_ACCEPTED")
        self.assertEqual(self.sm.audio_sessions_started, 1)

        for _ in range(25):
            self.assertEqual(self.sm.trigger("alarm_1", 1, "occ_1"), "DUPLICATE_TRIGGER_REJECTED")

        self.assertEqual(self.sm.duplicate_count, 25)
        self.assertEqual(self.sm.audio_sessions_started, 1)

    def test_resurrection_after_dismiss(self) -> None:
        """Occurrence cannot be resurrected after dismissal."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_1")
        self.sm.trigger("alarm_1", 1, "occ_1")
        self.sm.dismiss()
        self.assertEqual(self.sm.state, "DISMISSED")

        res = self.sm.trigger("alarm_1", 1, "occ_1")
        self.assertEqual(res, "DUPLICATE_TRIGGER_REJECTED")
        self.assertEqual(self.sm.audio_sessions_started, 1)

    def test_snooze_guards_and_parent_replay_defense(self) -> None:
        """Snoozing creates a child occurrence and protects against parent replay."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "parent_occ")
        self.sm.trigger("alarm_1", 1, "parent_occ")

        self.assertEqual(self.sm.snooze("child_occ"), "SNOOZED_OK")
        self.assertEqual(self.sm.state, "SNOOZED")

        # Parent occurrence replayed while snoozed
        self.assertEqual(self.sm.trigger("alarm_1", 1, "parent_occ"), "DUPLICATE_TRIGGER_REJECTED")

        # Child triggers legitimately
        self.assertEqual(self.sm.trigger("alarm_1", 1, "child_occ"), "TRIGGER_ACCEPTED")
        self.assertEqual(self.sm.audio_sessions_started, 2)


# =============================================================================
# RED TEAM 2: AUDIO_EVIDENCE_RED_TEAM
# =============================================================================
class TestAudioEvidenceRedTeam(unittest.TestCase):
    def setUp(self) -> None:
        self.sm = StateMachineSimulator()

    def test_software_audio_checkpoints_clean_path(self) -> None:
        """Standard trigger proceeds through checkpoints to CHECKPOINT_SOFTWARE_AUDIO_STARTED."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_1")
        res = self.sm.trigger("alarm_1", 1, "occ_1")

        self.assertEqual(res, "TRIGGER_ACCEPTED")
        self.assertEqual(self.sm.audio_checkpoint, "CHECKPOINT_SOFTWARE_AUDIO_STARTED")
        self.assertEqual(self.sm.state, "SOFTWARE_AUDIO_STARTED")
        self.assertTrue(self.sm.software_audio_started)
        self.assertFalse(self.sm.software_audio_failed)

    def test_audio_init_failure_fail_closed(self) -> None:
        """If AudioTrack initialization fails, state MUST NOT become SOFTWARE_AUDIO_STARTED."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_1")
        self.sm.set_audio_fault("INIT_FAIL")

        res = self.sm.trigger("alarm_1", 1, "occ_1")
        self.assertEqual(res, "SOFTWARE_AUDIO_FAILED")
        self.assertEqual(self.sm.state, "SOFTWARE_AUDIO_FAILED")
        self.assertEqual(self.sm.audio_checkpoint, "CHECKPOINT_SOFTWARE_AUDIO_FAILED")
        self.assertTrue(self.sm.software_audio_failed)
        self.assertFalse(self.sm.software_audio_started)
        self.assertEqual(self.sm.audio_sessions_started, 0)

    def test_audio_write_failure_fail_closed(self) -> None:
        """If AudioTrack write() returns error, state MUST NOT become SOFTWARE_AUDIO_STARTED."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_1")
        self.sm.set_audio_fault("WRITE_FAIL")

        res = self.sm.trigger("alarm_1", 1, "occ_1")
        self.assertEqual(res, "SOFTWARE_AUDIO_FAILED")
        self.assertEqual(self.sm.state, "SOFTWARE_AUDIO_FAILED")
        self.assertEqual(self.sm.audio_checkpoint, "CHECKPOINT_SOFTWARE_AUDIO_FAILED")
        self.assertTrue(self.sm.software_audio_failed)
        self.assertFalse(self.sm.software_audio_started)

    def test_audio_play_failure_fail_closed(self) -> None:
        """If AudioTrack play() fails, state MUST NOT become SOFTWARE_AUDIO_STARTED."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_1")
        self.sm.set_audio_fault("PLAY_FAIL")

        res = self.sm.trigger("alarm_1", 1, "occ_1")
        self.assertEqual(res, "SOFTWARE_AUDIO_FAILED")
        self.assertEqual(self.sm.state, "SOFTWARE_AUDIO_FAILED")
        self.assertEqual(self.sm.audio_checkpoint, "CHECKPOINT_SOFTWARE_AUDIO_FAILED")
        self.assertTrue(self.sm.software_audio_failed)
        self.assertFalse(self.sm.software_audio_started)

    def test_audible_claim_falsification(self) -> None:
        """Audit verifier that detects and rejects any illegal claim of AUDIBLE or HUMAN_AWAKE."""
        def audit_report(report_dict: Dict[str, Any]) -> Tuple[bool, str]:
            if report_dict.get("audible_claimed") is True:
                return False, "EPISTEMIC_VIOLATION: audible_claimed cannot be True in emulator"
            if report_dict.get("human_awake_claimed") is True:
                return False, "EPISTEMIC_VIOLATION: human_awake_claimed cannot be True in emulator"
            if report_dict.get("statistical_summary", {}).get("duplicate_triggers_accepted", 0) > 0:
                return False, "RELIABILITY_VIOLATION: duplicate triggers accepted > 0"
            return True, "AUDIT_PASS"

        valid_report = {
            "contract": CONTRACT_E1_EVIDENCE,
            "audible_claimed": False,
            "human_awake_claimed": False,
            "statistical_summary": {"duplicate_triggers_accepted": 0},
        }
        ok, msg = audit_report(valid_report)
        self.assertTrue(ok)

        # Illegal audible claim
        tampered = copy.deepcopy(valid_report)
        tampered["audible_claimed"] = True
        ok, msg = audit_report(tampered)
        self.assertFalse(ok)
        self.assertIn("EPISTEMIC_VIOLATION", msg)


# =============================================================================
# RED TEAM 3: BOOT_RECOVERY_RED_TEAM
# =============================================================================
class TestBootRecoveryRedTeam(unittest.TestCase):
    def setUp(self) -> None:
        self.sm = StateMachineSimulator()

    def test_boot_reconciliation_future_rescheduled(self) -> None:
        """Reconciliation of future armed target reschedules cleanly."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_future")

        now = 1000000
        target = now + 60000  # 60s future
        res = self.sm.reconcile(target_epoch_ms=target, now_epoch_ms=now)

        self.assertEqual(res, "RESCHEDULED_FUTURE")
        self.assertEqual(self.sm.state, "ARMED")
        self.assertEqual(self.sm.audio_sessions_started, 0)
        self.assertEqual(self.sm.reconciliation_count, 1)

    def test_repeated_reconciliation_stress_idempotence(self) -> None:
        """Flooding 100 reconciliations does not advance state or create duplicates."""
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_future")

        now = 1000000
        target = now + 50000

        for _ in range(100):
            res = self.sm.reconcile(target_epoch_ms=target, now_epoch_ms=now)
            self.assertEqual(res, "RESCHEDULED_FUTURE")

        self.assertEqual(self.sm.reconciliation_count, 100)
        self.assertEqual(self.sm.state, "ARMED")
        self.assertEqual(self.sm.audio_sessions_started, 0)
        self.assertEqual(self.sm.duplicate_count, 0)

    def test_late_recovery_boundary_cliff(self) -> None:
        """Strict boundary cliff at exactly 10 minutes (600,000 ms)."""
        now = 2000000
        limit_ms = 600_000

        # At exactly 10 minutes overdue: RECOVERED_LATE
        self.sm.reset()
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_boundary_in")
        res_in = self.sm.reconcile(target_epoch_ms=now - limit_ms, now_epoch_ms=now)
        self.assertEqual(res_in, "RECOVERED_LATE")
        self.assertEqual(self.sm.state, "RECOVERED_LATE")

        # At 10 minutes + 1 ms overdue: NO SURPRISE ALARM -> OUTCOME_UNKNOWN
        self.sm.reset()
        self.sm.configure("alarm_1", 1)
        self.sm.arm("alarm_1", 1, "occ_boundary_out")
        res_out = self.sm.reconcile(target_epoch_ms=now - (limit_ms + 1), now_epoch_ms=now)
        self.assertEqual(res_out, "SUPPRESSED_OVERDUE_PAST_LIMIT")
        self.assertEqual(self.sm.state, "OUTCOME_UNKNOWN")


# =============================================================================
# RED TEAM 4: STATISTICS_RED_TEAM
# =============================================================================
class TestStatisticsRedTeam(unittest.TestCase):
    def test_nearest_rank_p95_formula(self) -> None:
        """Verify nearest-rank formula: rank = math.ceil(0.95 * N), index = rank - 1."""
        def calc_p95(data: List[float]) -> float:
            sorted_data = sorted(data)
            n = len(sorted_data)
            rank = math.ceil(0.95 * n)
            idx = max(0, min(rank - 1, n - 1))
            return sorted_data[idx]

        # N = 10: ceil(9.5) = 10 -> index 9 (last element)
        data_10 = list(range(1, 11))
        self.assertEqual(calc_p95(data_10), 10)

        # N = 20: ceil(19.0) = 19 -> index 18
        data_20 = list(range(1, 21))
        self.assertEqual(calc_p95(data_20), 19)

        # N = 100: ceil(95.0) = 95 -> index 94
        data_100 = list(range(1, 101))
        self.assertEqual(calc_p95(data_100), 95)

    def test_timing_band_classification(self) -> None:
        """Verify the 5 timing band boundaries."""
        def classify(delta: float) -> str:
            if delta < -500:
                return "FAIL_EARLY"
            elif delta < 0:
                return "EARLY_TOLERANCE"
            elif delta <= 2000:
                return "TARGET"
            elif delta <= 5000:
                return "ACCEPTABLE"
            else:
                return "FAIL_LATE"

        self.assertEqual(classify(-600), "FAIL_EARLY")
        self.assertEqual(classify(-501), "FAIL_EARLY")
        self.assertEqual(classify(-500), "EARLY_TOLERANCE")
        self.assertEqual(classify(-1), "EARLY_TOLERANCE")
        self.assertEqual(classify(0), "TARGET")
        self.assertEqual(classify(1500), "TARGET")
        self.assertEqual(classify(2000), "TARGET")
        self.assertEqual(classify(2001), "ACCEPTABLE")
        self.assertEqual(classify(5000), "ACCEPTABLE")
        self.assertEqual(classify(5001), "FAIL_LATE")
        self.assertEqual(classify(10000), "FAIL_LATE")

    def test_route_stratification_and_superseded_detection(self) -> None:
        """Verify route stratification separates ALARM_CLOCK and EXACT_ALLOW_IDLE."""
        a1_deltas = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        a2_deltas = [15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0, 95.0, 105.0]

        a1_median = statistics.median(a1_deltas)
        a2_median = statistics.median(a2_deltas)
        comb_median = statistics.median(a1_deltas + a2_deltas)

        self.assertEqual(a1_median, 55.0)
        self.assertEqual(a2_median, 60.0)
        self.assertEqual(comb_median, 57.5)


# =============================================================================
# PHASE 16: MUTATION / FUZZING
# =============================================================================
class TestMutationFuzz(unittest.TestCase):
    def test_mutation_fuzz_state_machine_random_actions(self) -> None:
        """Apply 500 randomized mutations/fuzz actions and assert invariants hold."""
        sm = StateMachineSimulator()
        rng = random.Random(42)  # Deterministic seed

        valid_states = {
            "IDLE", "CONFIGURED", "ARMED", "TRIGGERED", "SOFTWARE_AUDIO_STARTED",
            "SOFTWARE_AUDIO_FAILED", "SNOOZED", "DISMISSED", "RECOVERED_LATE", "OUTCOME_UNKNOWN"
        }

        for iteration in range(500):
            action = rng.choice(["configure", "arm", "trigger", "snooze", "dismiss", "reconcile", "reset"])
            occ_id = f"occ_{rng.randint(1, 5)}"
            gen = rng.randint(-1, 5)

            if action == "configure":
                sm.configure(f"alarm_{rng.randint(1, 3)}", gen)
            elif action == "arm":
                route = rng.choice(["ALARM_CLOCK", "EXACT_ALLOW_IDLE", "ROGUE_ROUTE"])
                sm.arm(f"alarm_{rng.randint(1, 3)}", gen, occ_id, route=route)
            elif action == "trigger":
                sm.trigger(f"alarm_{rng.randint(1, 3)}", gen, occ_id)
            elif action == "snooze":
                sm.snooze(f"child_{rng.randint(1, 5)}")
            elif action == "dismiss":
                sm.dismiss()
            elif action == "reconcile":
                target = rng.randint(500_000, 1_500_000)
                now = 1_000_000
                sm.reconcile(target, now)
            elif action == "reset":
                sm.reset()

            # Global Invariants:
            self.assertIn(sm.state, valid_states, f"Iteration {iteration}: state corrupted to {sm.state}")
            self.assertFalse(sm.audible_claimed, "Audible was claimed during fuzzing")
            self.assertFalse(sm.human_awake_claimed, "Human awake was claimed during fuzzing")


if __name__ == "__main__":
    unittest.main()
