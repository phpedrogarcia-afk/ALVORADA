from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import MagicMock, patch

from e1_scenario_runner import (
    CONTRACT_E1_EVIDENCE,
    APPROVED_LOCK_DIGEST,
    E1ScenarioRunner,
    E1ScenarioError,
)


class TestE1ScenarioRunner(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name) / "artifacts"
        self.runner = E1ScenarioRunner(
            serial="emulator-5554",
            adb_bin="adb",
            output_dir=self.output_dir,
            repo_sha="mock_sha_123",
            run_id="run_test_456",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @patch.object(E1ScenarioRunner, "poll_for_state")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_scenario_a1_baseline(self, mock_cmd: MagicMock, mock_poll: MagicMock) -> None:
        mock_cmd.side_effect = lambda cmd, extras=None: {
            "state": "CONFIGURED" if cmd == "CONFIGURE" else "ARMED" if cmd == "ARM" else "IDLE"
        }
        mock_poll.return_value = {
            "state": "SOFTWARE_AUDIO_STARTED",
            "duplicate_trigger_count": 0,
            "delivery_delta_ms": 12,
            "trigger_to_software_audio_ms": 45,
        }

        res = self.runner.run_scenario_a1(repetitions=3)
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(len(res["details"]), 3)
        self.assertEqual(res["details"][0]["delivery_delta_ms"], 12)

    @patch.object(E1ScenarioRunner, "get_app_pid")
    @patch.object(E1ScenarioRunner, "poll_for_state")
    @patch.object(E1ScenarioRunner, "run_adb")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_scenario_a2_process_death(
        self, mock_cmd: MagicMock, mock_adb: MagicMock, mock_poll: MagicMock, mock_pid: MagicMock
    ) -> None:
        mock_cmd.side_effect = lambda cmd, extras=None: {
            "state": "CONFIGURED" if cmd == "CONFIGURE" else "ARMED" if cmd == "ARM" else "IDLE"
        }
        mock_adb.return_value = (0, "killed", "")
        # For rep 1: before_kill="1001", after kill=None, after trigger="1002"
        # For rep 2: before_kill="1002", after kill=None, after trigger="1003"
        mock_pid.side_effect = ["1001", None, "1002", "1002", None, "1003"]
        mock_poll.return_value = {
            "state": "SOFTWARE_AUDIO_STARTED",
            "duplicate_trigger_count": 0,
            "delivery_delta_ms": 15,
            "trigger_to_software_audio_ms": 50,
        }

        res = self.runner.run_scenario_a2(repetitions=2)
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(len(res["details"]), 2)
        self.assertEqual(res["details"][0]["pid_before_kill"], "1001")
        self.assertTrue(res["details"][0]["pid_absent_confirmed"])
        self.assertEqual(res["details"][0]["pid_after_trigger"], "1002")
        self.assertTrue(res["details"][0]["pid_absence_proven"])
        self.assertTrue(res["details"][0]["new_process_pid_proven"])

    @patch.object(E1ScenarioRunner, "poll_for_state")
    @patch.object(E1ScenarioRunner, "get_state")
    @patch.object(E1ScenarioRunner, "run_adb")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_scenario_b1_guest_reboot(
        self, mock_cmd: MagicMock, mock_adb: MagicMock, mock_state: MagicMock, mock_poll: MagicMock
    ) -> None:
        last_occ = [""]
        def fake_cmd(cmd: str, extras: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            if cmd == "ARM" and extras:
                last_occ[0] = extras.get("occurrence_id", "")
            if cmd == "DUMP_STATE":
                return {
                    "state": "ARMED",
                    "boot_received_action": "android.intent.action.BOOT_COMPLETED",
                    "boot_receiver_invocation_epoch_ms": int(time.time() * 1000) + 1000,
                    "reconciliation_count": 1,
                    "post_reconciliation_result": "RESCHEDULED_FUTURE",
                    "pre_reconciliation_state": "ARMED",
                }
            return {"state": "CONFIGURED" if cmd == "CONFIGURE" else "ARMED" if cmd == "ARM" else "IDLE"}

        mock_cmd.side_effect = fake_cmd
        def fake_adb(*args: Any, **kwargs: Any) -> tuple[int, str, str]:
            if "sys.boot_completed" in args:
                return (0, "1\n", "")
            elif "pm" in args and "path" in args:
                return (0, "package:/data/app/org.alvorada.reliability.wakecore\n", "")
            elif "logcat" in args and "-d" in args:
                return (0, "01-01 10:00:00.000 WakeBootReceiver: action=android.intent.action.BOOT_COMPLETED\n", "")
            elif "dumpsys" in args and "alarm" in args:
                return (0, f"Batch[...]: PendingIntent{{... org.alvorada.reliability.wakecore ... {last_occ[0]} ...}}\n", "")
            return (0, "", "")

        mock_adb.side_effect = fake_adb
        mock_state.return_value = {
            "state": "ARMED",
            "boot_received_action": "android.intent.action.BOOT_COMPLETED",
            "boot_receiver_invocation_epoch_ms": 1700000000000,
            "reconciliation_count": 1,
            "post_reconciliation_result": "RESCHEDULED_FUTURE",
            "pre_reconciliation_state": "ARMED",
        }
        mock_poll.return_value = {
            "state": "SOFTWARE_AUDIO_STARTED",
            "duplicate_trigger_count": 0,
            "delivery_delta_ms": 25,
            "trigger_to_software_audio_ms": 40,
        }

        with patch("time.sleep"):
            res = self.runner.run_scenario_b1(repetitions=1)
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(len(res["details"]), 1)
        det = res["details"][0]
        self.assertTrue(det["surface_a_logcat_verified"])
        self.assertTrue(det["surface_b_alarmmanager_reschedule_verified"])
        self.assertTrue(det["surface_c_dump_state_verified"])
        self.assertTrue(det["delivery_verified"])


    @patch.object(E1ScenarioRunner, "get_state")
    @patch.object(E1ScenarioRunner, "poll_for_state")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_scenario_a3_duplicate_defense(self, mock_cmd: MagicMock, mock_poll: MagicMock, mock_state: MagicMock) -> None:
        mock_poll.return_value = {
            "state": "SOFTWARE_AUDIO_STARTED",
            "software_audio_started_at_epoch_ms": 1000000,
        }
        mock_state.return_value = {
            "state": "SOFTWARE_AUDIO_STARTED",
            "duplicate_trigger_count": 10,
            "software_audio_started_at_epoch_ms": 1000000,
        }

        res = self.runner.run_scenario_a3(injections=10)
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["duplicates_rejected"], 10)

    @patch.object(E1ScenarioRunner, "get_state")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_scenario_a4_stale_generation(self, mock_cmd: MagicMock, mock_state: MagicMock) -> None:
        state_holder = {
            "state": "ARMED",
            "alarm_id": "alarm_a4",
            "generation": 2,
            "occurrence_id": "",
            "stale_generation_rejection_count": 10,
            "future_generation_rejection_count": 10,
            "invalid_generation_rejection_count": 10,
            "wrong_alarm_id_rejection_count": 10,
            "wrong_occurrence_id_rejection_count": 10,
            "invalid_identity_rejection_count": 10,
        }
        def fake_cmd(cmd: str, extras: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            if cmd == "ARM" and extras:
                state_holder["occurrence_id"] = extras.get("occurrence_id", "")
            return state_holder

        mock_cmd.side_effect = fake_cmd
        mock_state.side_effect = lambda: dict(state_holder)

        res = self.runner.run_scenario_a4(cases=10)
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["stale_rejections"], 10)
        self.assertEqual(res["future_generation_rejections"], 10)
        self.assertTrue(res["authority_state_preserved"])

    @patch.object(E1ScenarioRunner, "poll_for_state")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_scenario_a5_snooze(self, mock_cmd: MagicMock, mock_poll: MagicMock) -> None:
        mock_poll.side_effect = [
            {"state": "SOFTWARE_AUDIO_STARTED", "occurrence_id": "parent_occ"},
            {"state": "SOFTWARE_AUDIO_STARTED", "occurrence_id": "child_snooze_123"},
        ]
        mock_cmd.side_effect = lambda cmd, extras=None: {
            "state": "SNOOZED",
            "occurrence_id": "child_snooze_123",
        } if cmd == "SNOOZE" else {"state": "ARMED"}

        res = self.runner.run_scenario_a5()
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["production_contract_delay_ms"], 300000)
        self.assertEqual(res["empirical_test_delay_ms"], 2500)
        self.assertFalse(res["real_five_minute_wait_executed"])

    @patch.object(E1ScenarioRunner, "poll_for_state")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_scenario_a6_dismiss(self, mock_cmd: MagicMock, mock_poll: MagicMock) -> None:
        mock_poll.return_value = {"state": "SOFTWARE_AUDIO_STARTED"}
        mock_cmd.side_effect = lambda cmd, extras=None: {
            "state": "DISMISSED",
            "civil_schedule": "07:00",
            "alarm_id": "alarm_a6",
        } if cmd == "DISMISS" else {"state": "CONFIGURED"}

        res = self.runner.run_scenario_a6()
        self.assertEqual(res["result"], "PASS")
        self.assertTrue(res["recurring_schedule_preserved"])

    @patch.object(E1ScenarioRunner, "get_state")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_scenario_b2_reconciliation_idempotence(self, mock_cmd: MagicMock, mock_state: MagicMock) -> None:
        mock_state.return_value = {
            "state": "ARMED",
            "reconciliation_count": 10,
            "duplicate_trigger_count": 0,
        }

        res = self.runner.run_scenario_b2(invocations=10)
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["reconciliation_count"], 10)

    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_scenario_b3_late_recovery(self, mock_cmd: MagicMock) -> None:
        mock_cmd.side_effect = [
            {"state": "IDLE"}, # reset
            {"state": "CONFIGURED"},
            {"state": "ARMED"},
            {"state": "RECOVERED_LATE", "reconciliation_result": "RECOVERED_LATE"},
            {"state": "IDLE"}, # reset
            {"state": "CONFIGURED"},
            {"state": "ARMED"},
            {"state": "OUTCOME_UNKNOWN", "reconciliation_result": "SUPPRESSED_OVERDUE_PAST_LIMIT"},
        ]

        res = self.runner.run_scenario_b3()
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["case_under_10min_result"], "RECOVERED_LATE")
        self.assertEqual(res["case_over_10min_result"], "OUTCOME_UNKNOWN")

    @patch.object(E1ScenarioRunner, "poll_for_state")
    @patch.object(E1ScenarioRunner, "reset_state")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_audio_failure_injection(self, mock_cmd: MagicMock, mock_reset: MagicMock, mock_poll: MagicMock) -> None:
        mock_poll.return_value = {
            "state": "SOFTWARE_AUDIO_FAILED",
            "software_audio_failed": True,
            "software_audio_checkpoint": "CHECKPOINT_SOFTWARE_AUDIO_FAILED",
        }
        res = self.runner.run_audio_failure_injection()
        self.assertEqual(res["result"], "PASS")
        self.assertTrue(res["audio_init_failure_tested"])
        self.assertTrue(res["audio_write_failure_tested"])
        self.assertTrue(res["audio_play_failure_tested"])
        self.assertTrue(res["software_audio_false_positive_closed"])

    @patch.object(E1ScenarioRunner, "get_state")
    @patch.object(E1ScenarioRunner, "reset_state")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_route_validation(self, mock_cmd: MagicMock, mock_reset: MagicMock, mock_state: MagicMock) -> None:
        mock_state.return_value = {"state": "CONFIGURED"}
        res = self.runner.run_route_validation()
        self.assertEqual(res["result"], "PASS")
        self.assertTrue(res["route_fail_closed"])
        self.assertEqual(res["unknown_routes_accepted"], 0)

    @patch.object(E1ScenarioRunner, "get_app_pid")
    @patch.object(E1ScenarioRunner, "run_adb")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_phase_11_force_stop(self, mock_cmd: MagicMock, mock_adb: MagicMock, mock_pid: MagicMock) -> None:
        mock_cmd.return_value = {"state": "ARMED"}
        mock_adb.side_effect = [
            (0, "force-stopped", ""), # am force-stop
            (0, "Package [org.alvorada.reliability.wakecore] (xxx): stopped=true", ""), # dumpsys
        ]
        mock_pid.return_value = None

        with patch("time.sleep"): # avoid actual 22s sleep
            res = self.runner.run_phase_11_force_stop()
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["causal_classification"], "EXPECTED_PLATFORM_CANCELLATION")

    @patch.object(E1ScenarioRunner, "run_adb")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_phase_12_readiness_decay(self, mock_cmd: MagicMock, mock_adb: MagicMock) -> None:
        mock_adb.return_value = (0, "appops success", "")
        mock_cmd.return_value = {"state": "READINESS_DECAY_BLOCKED"}

        with patch("time.sleep"):
            res = self.runner.run_phase_12_readiness_decay()
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["causal_classification"], "READINESS_DECAY_ENFORCED")
        self.assertEqual(res["readiness_decay_result"], "OBSERVED")

    @patch.object(E1ScenarioRunner, "run_scenario_a1")
    @patch.object(E1ScenarioRunner, "run_scenario_a2")
    @patch.object(E1ScenarioRunner, "run_scenario_a3")
    @patch.object(E1ScenarioRunner, "run_scenario_a4")
    @patch.object(E1ScenarioRunner, "run_scenario_a5")
    @patch.object(E1ScenarioRunner, "run_scenario_a6")
    @patch.object(E1ScenarioRunner, "run_scenario_b2")
    @patch.object(E1ScenarioRunner, "run_scenario_b3")
    @patch.object(E1ScenarioRunner, "run_audio_failure_injection")
    @patch.object(E1ScenarioRunner, "run_route_validation")
    @patch.object(E1ScenarioRunner, "run_phase_11_force_stop")
    @patch.object(E1ScenarioRunner, "run_phase_12_readiness_decay")
    def test_run_all_end_to_end(
        self,
        mock_p12: MagicMock,
        mock_p11: MagicMock,
        mock_route: MagicMock,
        mock_audio: MagicMock,
        mock_b3: MagicMock,
        mock_b2: MagicMock,
        mock_a6: MagicMock,
        mock_a5: MagicMock,
        mock_a4: MagicMock,
        mock_a3: MagicMock,
        mock_a2: MagicMock,
        mock_a1: MagicMock,
    ) -> None:
        mock_a1.return_value = {
            "result": "PASS",
            "repetitions": 10,
            "details": [{"delivery_delta_ms": 10 + i, "trigger_to_software_audio_ms": 40 + i} for i in range(10)],
        }
        mock_a2.return_value = {
            "result": "PASS",
            "repetitions": 10,
            "details": [{"delivery_delta_ms": 12 + i, "trigger_to_software_audio_ms": 42 + i} for i in range(10)],
        }
        mock_a3.return_value = {"result": "PASS", "duplicates_rejected": 10}
        mock_a4.return_value = {"result": "PASS", "stale_rejections": 10}
        mock_a5.return_value = {"result": "PASS", "production_contract_delay_ms": 300000, "empirical_test_delay_ms": 2500}
        mock_a6.return_value = {"result": "PASS"}
        mock_b2.return_value = {"result": "PASS"}
        mock_b3.return_value = {"result": "PASS"}
        mock_audio.return_value = {"result": "PASS"}
        mock_route.return_value = {"result": "PASS"}
        mock_p11.return_value = {"result": "PASS", "causal_classification": "EXPECTED_PLATFORM_CANCELLATION"}
        mock_p12.return_value = {"result": "PASS", "causal_classification": "READINESS_DECAY_ENFORCED"}

        report = self.runner.run_all(skip_reboot=True)
        self.assertEqual(report["overall_status"], "PASS")

        # Verify stratified statistics
        stats = report["statistical_summary"]
        self.assertIn("a1_alarm_clock", stats)
        self.assertIn("a2_exact_allow_idle", stats)
        self.assertIn("combined", stats)
        self.assertEqual(stats["old_statistical_derivation_superseded"], "RUN_35758945392_SUPERSEDED")

        # Verify artifacts were created on disk
        self.assertTrue((self.output_dir / "e1-scenario-report.json").is_file())
        self.assertTrue((self.output_dir / "e1-scenario-report.txt").is_file())
        self.assertTrue((self.output_dir / "manifest.json").is_file())
        self.assertTrue((self.output_dir / "checksums.sha256").is_file())

    def test_run_lane_b1_direct_boot_preunlock(self) -> None:
        self.runner.run_adb = MagicMock(return_value=(0, "true", ""))
        res = self.runner.run_lane_b1_direct_boot_preunlock()
        self.assertEqual(res["direct_boot_preunlock"], "REFERENCE_IMAGE_PREUNLOCK_CAPABILITY_UNAVAILABLE")
        self.assertEqual(res["ce_storage_required"], "NO")

    def test_run_lane_b2_civil_time_engine(self) -> None:
        res = self.runner.run_lane_b2_civil_time_engine()
        self.assertEqual(res["civil_time_engine"], "PASS")
        self.assertEqual(res["timezone_change"], "PASS")
        self.assertEqual(res["dst_gap"], "PASS")
        self.assertEqual(res["dst_fold"], "PASS")

    def test_run_lane_b3_exact_alarm_readiness(self) -> None:
        self.runner.send_broadcast_cmd = MagicMock(return_value={"can_schedule_exact_alarms": True})
        self.runner.run_adb = MagicMock(return_value=(0, "", ""))
        res = self.runner.run_lane_b3_exact_alarm_readiness()
        self.assertEqual(res["readiness_decay_result"], "READINESS_DECAY_ENFORCED")
        self.assertEqual(res["result"], "PASS")

    def test_run_lane_b4_wake_session_lifecycle(self) -> None:
        self.runner.send_broadcast_cmd = MagicMock(return_value={
            "notification_permission_granted": True,
            "notification_channel_enabled": True,
            "full_screen_intent_capable": True,
            "audio_capable": True,
            "wake_session_checkpoint": "WAKE_SESSION_DISMISSED"
        })
        self.runner.poll_for_state = MagicMock(return_value={"wake_session_checkpoint": "SOFTWARE_AUDIO_CONTINUING"})
        res = self.runner.run_lane_b4_wake_session_lifecycle()
        self.assertEqual(res["wake_session"], "PASS")
        self.assertEqual(res["notification_lifecycle"], "PASS")
        self.assertEqual(res["background_session_start"], "PASS")
        self.assertEqual(res["audio_session_continuity"], "PASS")


if __name__ == "__main__":
    unittest.main()
