#!/usr/bin/env python3
"""Unit tests for P1-P10 Proof Runner (proof_runner.py)."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from proof_runner import (
    CONTRACT_PROOF_SEQUENCE,
    ProofExecutionError,
    ProofRunner,
)


class TestProofRunner(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.sdk_root = self.root / "sdk"
        self.output_dir = self.root / "evidence" / "p1-p10"
        self.sdk_root.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup mock binaries
        self.emu_bin = self.sdk_root / "emulator" / "emulator"
        self.emu_bin.parent.mkdir(parents=True, exist_ok=True)
        self.emu_bin.write_bytes(b"mock_emulator")

        self.adb_bin = self.sdk_root / "platform-tools" / "adb"
        self.adb_bin.parent.mkdir(parents=True, exist_ok=True)
        self.adb_bin.write_bytes(b"mock_adb")

        self.runner = ProofRunner(
            sdk_root=self.sdk_root,
            output_dir=self.output_dir,
            repo_sha="test_sha_12345",
            run_id="test_run_999",
            timeout_boot_seconds=5,
            startup_window_seconds=1,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @patch.object(ProofRunner, "execute_p1")
    def test_p1_failure_classification(self, mock_p1: MagicMock) -> None:
        mock_p1.side_effect = ProofExecutionError("P1", "AVD_CONFIG_FAILURE", "Missing config")
        with self.assertRaises(ProofExecutionError) as ctx:
            self.runner.run_all_proofs()
        self.assertEqual(ctx.exception.gate, "P1")
        self.assertEqual(ctx.exception.classification, "AVD_CONFIG_FAILURE")

        report_file = self.output_dir / "proof-report.json"
        self.assertTrue(report_file.is_file())
        with open(report_file) as f:
            rep = json.load(f)
        self.assertEqual(rep["overall_status"], "FAIL")
        self.assertEqual(rep["failure"]["gate"], "P1")

    @patch("subprocess.Popen")
    def test_p2_failure_immediate_exit(self, mock_popen: MagicMock) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.poll.return_value = 1  # exited immediately
        mock_proc.stderr.read.return_value = "Fatal GPU error"
        mock_popen.return_value = mock_proc

        with self.assertRaises(ProofExecutionError) as ctx:
            self.runner.execute_p2()
        self.assertEqual(ctx.exception.gate, "P2")
        self.assertEqual(ctx.exception.classification, "EMULATOR_START_FAILURE")

    @patch.object(ProofRunner, "_run_adb")
    def test_p4_adb_transport_failure(self, mock_adb: MagicMock) -> None:
        # No devices found
        mock_adb.return_value = MagicMock(returncode=0, stdout="List of devices attached\n\n", stderr="")
        with self.assertRaises(ProofExecutionError) as ctx:
            self.runner._find_active_serial(timeout_seconds=2)
        self.assertEqual(ctx.exception.gate, "P4")
        self.assertEqual(ctx.exception.classification, "ADB_TRANSPORT_FAILURE")

    @patch.object(ProofRunner, "_run_adb")
    def test_p5_boot_failure_invalid_boot_id(self, mock_adb: MagicMock) -> None:
        def side_effect(args, **kwargs):
            if "sys.boot_completed" in args:
                return MagicMock(returncode=0, stdout="1\n", stderr="")
            elif "pm" in args and "path" in args:
                return MagicMock(returncode=0, stdout="package:/system/framework/framework-res.apk\n", stderr="")
            elif "boot_id" in args:
                return MagicMock(returncode=0, stdout="INVALID_NON_UUID\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_adb.side_effect = side_effect
        with self.assertRaises(ProofExecutionError) as ctx:
            self.runner._wait_for_boot_completed(timeout_seconds=2)
        self.assertEqual(ctx.exception.gate, "P5")
        self.assertEqual(ctx.exception.classification, "ANDROID_BOOT_FAILURE")

    @patch.object(ProofRunner, "_run_adb")
    def test_p7_install_failure(self, mock_adb: MagicMock) -> None:
        self.runner.device_serial = "emulator-5554"
        apk_path = self.root / "fake.apk"
        apk_path.write_bytes(b"apk")
        self.runner.built_apk_path = apk_path

        mock_adb.return_value = MagicMock(returncode=1, stdout="Failure [INSTALL_FAILED_VERIFICATION_FAILURE]\n", stderr="")
        with self.assertRaises(ProofExecutionError) as ctx:
            self.runner.execute_p7()
        self.assertEqual(ctx.exception.gate, "P7")
        self.assertEqual(ctx.exception.classification, "APK_INSTALL_FAILURE")

    @patch.object(ProofRunner, "_run_adb")
    def test_p8_execute_failure(self, mock_adb: MagicMock) -> None:
        self.runner.device_serial = "emulator-5554"
        mock_adb.return_value = MagicMock(returncode=1, stdout="Broadcast completed: result=0\n", stderr="Error")
        with self.assertRaises(ProofExecutionError) as ctx:
            self.runner.execute_p8()
        self.assertEqual(ctx.exception.gate, "P8")
        self.assertEqual(ctx.exception.classification, "CODE_FAILURE")

    @patch.object(ProofRunner, "_run_adb")
    @patch.object(ProofRunner, "_stop_emulator_process")
    @patch.object(ProofRunner, "_start_emulator_process")
    def test_p9_persistence_failure_boot_id_unchanged(
        self, mock_start: MagicMock, mock_stop: MagicMock, mock_adb: MagicMock
    ) -> None:
        self.runner.active_process = MagicMock()
        self.runner.active_process.poll.return_value = None
        self.runner.boot_id_p5 = "c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c"

        # Simulate same boot_id returned after cold start
        def side_effect(args, **kwargs):
            cmd_str = " ".join(str(a) for a in args)
            if "devices" in cmd_str:
                return MagicMock(returncode=0, stdout="List of devices attached\nemulator-5554\tdevice\n", stderr="")
            if "sys.boot_completed" in cmd_str:
                return MagicMock(returncode=0, stdout="1\n", stderr="")
            if "pm" in cmd_str and "path" in cmd_str:
                return MagicMock(returncode=0, stdout="package:/system/framework/framework-res.apk\n", stderr="")
            if "boot_id" in cmd_str:
                return MagicMock(returncode=0, stdout="c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_adb.side_effect = side_effect
        mock_start.return_value = MagicMock(poll=MagicMock(return_value=None))

        with self.assertRaises(ProofExecutionError) as ctx:
            self.runner.execute_p9()
        self.assertEqual(ctx.exception.gate, "P9")
        self.assertEqual(ctx.exception.classification, "PERSISTENCE_FAILURE")

    @patch.object(ProofRunner, "execute_p1")
    @patch.object(ProofRunner, "execute_p2")
    @patch.object(ProofRunner, "execute_p3")
    @patch.object(ProofRunner, "execute_p4")
    @patch.object(ProofRunner, "execute_p5")
    @patch.object(ProofRunner, "execute_p6")
    @patch.object(ProofRunner, "execute_p7")
    @patch.object(ProofRunner, "execute_p8")
    @patch.object(ProofRunner, "execute_p9")
    @patch.object(ProofRunner, "execute_p10")
    def test_run_all_proofs_happy_path(
        self,
        mock_p10: MagicMock,
        mock_p9: MagicMock,
        mock_p8: MagicMock,
        mock_p7: MagicMock,
        mock_p6: MagicMock,
        mock_p5: MagicMock,
        mock_p4: MagicMock,
        mock_p3: MagicMock,
        mock_p2: MagicMock,
        mock_p1: MagicMock,
    ) -> None:
        mock_p1.return_value = {"gate": "P1", "result": "PASS"}
        mock_p2.return_value = {"gate": "P2", "result": "PASS"}
        mock_p3.return_value = {"gate": "P3", "result": "PASS"}
        mock_p4.return_value = {"gate": "P4", "result": "PASS"}
        mock_p5.return_value = {"gate": "P5", "result": "PASS"}
        mock_p6.return_value = {"gate": "P6", "result": "PASS"}
        mock_p7.return_value = {"gate": "P7", "result": "PASS"}
        mock_p8.return_value = {"gate": "P8", "result": "PASS"}
        mock_p9.return_value = {"gate": "P9", "result": "PASS"}
        mock_p10.return_value = {"gate": "P10", "result": "PASS"}

        rep = self.runner.run_all_proofs()
        self.assertEqual(rep["overall_status"], "PASS")
        self.assertEqual(rep["contract"], CONTRACT_PROOF_SEQUENCE)
        self.assertIn("P1", rep["gates"])
        self.assertIn("P10", rep["gates"])

        # Check files on disk
        self.assertTrue((self.output_dir / "proof-report.json").is_file())
        self.assertTrue((self.output_dir / "proof-report.txt").is_file())
        self.assertTrue((self.output_dir / "checksums.sha256").is_file())


if __name__ == "__main__":
    unittest.main()
