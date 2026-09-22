from __future__ import annotations

import json
from pathlib import Path
import tempfile
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

    @patch.object(E1ScenarioRunner, "poll_for_state")
    @patch.object(E1ScenarioRunner, "run_adb")
    @patch.object(E1ScenarioRunner, "send_broadcast_cmd")
    def test_scenario_a2_process_death(self, mock_cmd: MagicMock, mock_adb: MagicMock, mock_poll: MagicMock) -> None:
        mock_cmd.side_effect = lambda cmd, extras=None: {
            "state": "CONFIGURED" if cmd == "CONFIGURE" else "ARMED" if cmd == "ARM" else "IDLE"
        }
        mock_adb.return_value = (0, "killed", "")
        mock_poll.return_value = {
            "state": "SOFTWARE_AUDIO_STARTED",
            "duplicate_trigger_count": 0,
            "delivery_delta_ms": 15,
            "trigger_to_software_audio_ms": 50,
        }

        res = self.runner.run_scenario_a2(repetitions=2)
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(len(res["details"]), 2)

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
        mock_state.return_value = {
            "state": "CONFIGURED",
            "stale_generation_rejection_count": 10,
        }

        res = self.runner.run_scenario_a4(cases=10)
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["stale_rejections"], 10)

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
        self.assertEqual(res["contract_semantics"], "5_MINUTES")

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

        res = self.runner.run_phase_12_readiness_decay()
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["causal_classification"], "READINESS_DECAY_ENFORCED")

    @patch.object(E1ScenarioRunner, "run_scenario_a1")
    @patch.object(E1ScenarioRunner, "run_scenario_a2")
    @patch.object(E1ScenarioRunner, "run_scenario_a3")
    @patch.object(E1ScenarioRunner, "run_scenario_a4")
    @patch.object(E1ScenarioRunner, "run_scenario_a5")
    @patch.object(E1ScenarioRunner, "run_scenario_a6")
    @patch.object(E1ScenarioRunner, "run_scenario_b2")
    @patch.object(E1ScenarioRunner, "run_scenario_b3")
    @patch.object(E1ScenarioRunner, "run_phase_11_force_stop")
    @patch.object(E1ScenarioRunner, "run_phase_12_readiness_decay")
    def test_run_all_end_to_end(
        self,
        mock_p12: MagicMock,
        mock_p11: MagicMock,
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
        mock_a5.return_value = {"result": "PASS"}
        mock_a6.return_value = {"result": "PASS"}
        mock_b2.return_value = {"result": "PASS"}
        mock_b3.return_value = {"result": "PASS"}
        mock_p11.return_value = {"result": "PASS", "causal_classification": "EXPECTED_PLATFORM_CANCELLATION"}
        mock_p12.return_value = {"result": "PASS", "causal_classification": "READINESS_DECAY_ENFORCED"}

        report = self.runner.run_all(skip_reboot=True)
        self.assertEqual(report["overall_status"], "PASS")

        # Verify artifacts were created on disk
        self.assertTrue((self.output_dir / "e1-scenario-report.json").is_file())
        self.assertTrue((self.output_dir / "e1-scenario-report.txt").is_file())
        self.assertTrue((self.output_dir / "manifest.json").is_file())
        self.assertTrue((self.output_dir / "checksums.sha256").is_file())


if __name__ == "__main__":
    unittest.main()
