#!/usr/bin/env python3
"""ALVORADA P1-P10 Proof Runner

Executes and verifies the complete frozen proof sequence P1 through P10
on the locked API 36 Android Virtual Device (`alvorada_e1_api36_x86_64`):

    P1:  AVD CONFIG VALID
    P2:  EMULATOR PROCESS STARTED
    P3:  PROCESS REMAINS ALIVE THROUGH STARTUP WINDOW
    P4:  ADB TRANSPORT ESTABLISHED
    P5:  ANDROID BOOT READY (sys.boot_completed=1, PM responsive, boot_id captured)
    P6:  STATIC TEST FIXTURE BUILDS AGAINST API 36
    P7:  APK INSTALLS
    P8:  PACKAGE EXECUTES / BASIC CONTROL PATH WORKS
    P9:  TRUE COLD RESTART PERSISTENCE (no snapshot, no wipe-data, boot_id changes, apk persists)
    P10: CONTROLLED GUEST REBOOT (adb reboot, boot_id changes, apk persists, adb recovers)

Outputs canonical evidence artifacts:
    - proof-report.json
    - proof-report.txt
    - checksums.sha256
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from wave2_avd_manager import (
    AVD_NAME_DEFAULT,
    LOCKED_GPU_MODE,
    LOCKED_SYSTEM_IMAGE_PACKAGE,
    Wave2AvdManager,
    AvdInspectionError,
)
from fixture_builder import (
    PACKAGE_NAME as FIXTURE_PACKAGE_NAME,
    FixtureBuilder,
    FixtureBuildError,
)

CONTRACT_PROOF_SEQUENCE = "ALVORADA_P1_P10_PROOF_SEQUENCE_V1"

UUID_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class ProofExecutionError(Exception):
    """Raised when any proof gate fails."""

    def __init__(self, gate: str, classification: str, reason: str) -> None:
        super().__init__(f"{gate} FAILED [{classification}]: {reason}")
        self.gate = gate
        self.classification = classification
        self.reason = reason


class ProofRunner:
    def __init__(
        self,
        sdk_root: Optional[Path] = None,
        avd_name: str = AVD_NAME_DEFAULT,
        repo_sha: str = "",
        run_id: str = "",
        output_dir: Optional[Path] = None,
        timeout_boot_seconds: int = 240,
        startup_window_seconds: int = 15,
    ) -> None:
        self.sdk_root = (
            sdk_root
            or Path(os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or "/usr/local/lib/android/sdk")
        ).resolve()
        self.avd_name = avd_name
        self.repo_sha = repo_sha
        self.run_id = run_id
        self.output_dir = (
            output_dir
            or Path(__file__).resolve().parent.parent / "evidence" / "p1-p10"
        ).resolve()
        self.timeout_boot_seconds = timeout_boot_seconds
        self.startup_window_seconds = startup_window_seconds

        self.avd_manager = Wave2AvdManager(sdk_root=self.sdk_root, avd_name=self.avd_name)
        self.fixture_builder = FixtureBuilder(sdk_root=self.sdk_root)

        self.emulator_bin = self._resolve_emulator_binary()
        self.adb_bin = self._resolve_adb_binary()

        # Gate execution results
        self.results: Dict[str, Dict[str, Any]] = {}
        self.active_process: Optional[subprocess.Popen[Any]] = None
        self.device_serial: Optional[str] = None
        self.boot_id_p5: Optional[str] = None
        self.boot_id_p9: Optional[str] = None
        self.boot_id_p10: Optional[str] = None
        self.built_apk_path: Optional[Path] = None

    def _resolve_emulator_binary(self) -> Path:
        cand = self.sdk_root / "emulator" / "emulator"
        if cand.is_file():
            return cand
        cand_exe = self.sdk_root / "emulator" / "emulator.exe"
        if cand_exe.is_file():
            return cand_exe
        which = shutil.which("emulator")
        if which:
            return Path(which)
        return cand

    def _resolve_adb_binary(self) -> Path:
        cand = self.sdk_root / "platform-tools" / "adb"
        if cand.is_file():
            return cand
        cand_exe = self.sdk_root / "platform-tools" / "adb.exe"
        if cand_exe.is_file():
            return cand_exe
        which = shutil.which("adb")
        if which:
            return Path(which)
        return cand

    # =========================================================================
    # Process & ADB Helpers
    # =========================================================================

    def _start_emulator_process(self, no_snapshot: bool = True, wipe_data: bool = False) -> subprocess.Popen[Any]:
        cmd = [
            str(self.emulator_bin),
            "-avd",
            self.avd_name,
            "-no-window",
            "-no-audio",
            "-gpu",
            LOCKED_GPU_MODE,
            "-no-boot-anim",
        ]
        if no_snapshot:
            cmd.append("-no-snapshot")
        if wipe_data:
            cmd.append("-wipe-data")

        # In Linux runner with KVM available, emulator uses KVM automatically or with -accel on
        if os.path.exists("/dev/kvm"):
            cmd.extend(["-accel", "on"])

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return proc

    def _stop_emulator_process(self, proc: Optional[subprocess.Popen[Any]] = None) -> None:
        target = proc or self.active_process
        if target is None:
            return

        # Try graceful shutdown via adb emu kill if device is known
        if self.device_serial:
            try:
                subprocess.run(
                    [str(self.adb_bin), "-s", self.device_serial, "emu", "kill"],
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
            except Exception:
                pass

        # Give it a moment to terminate gracefully
        try:
            target.wait(timeout=5)
        except subprocess.TimeoutExpired:
            target.terminate()
            try:
                target.wait(timeout=5)
            except subprocess.TimeoutExpired:
                target.kill()
                target.wait(timeout=5)

        if target == self.active_process:
            self.active_process = None

    def _run_adb(self, args: List[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        cmd = [str(self.adb_bin)]
        if self.device_serial and args and args[0] != "devices":
            cmd.extend(["-s", self.device_serial])
        cmd.extend(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)

    def _find_active_serial(self, timeout_seconds: int = 60) -> str:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            res = self._run_adb(["devices"])
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines()[1:]:
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[1] == "device":
                        return parts[0]
            time.sleep(2)
        raise ProofExecutionError("P4", "ADB_TRANSPORT_FAILURE", f"No device reached 'device' state within {timeout_seconds}s")

    def _wait_for_boot_completed(self, gate: str = "P5", timeout_seconds: int = 240) -> str:
        """Poll until sys.boot_completed=1 and Package Manager responds. Return boot_id."""
        deadline = time.time() + timeout_seconds
        boot_completed = False
        pm_ready = False

        while time.time() < deadline:
            # Check sys.boot_completed
            res_bc = self._run_adb(["shell", "getprop", "sys.boot_completed"])
            if res_bc.returncode == 0 and res_bc.stdout.strip() == "1":
                boot_completed = True

            # If boot completed, verify PM responsive
            if boot_completed:
                res_pm = self._run_adb(["shell", "pm", "path", "android"])
                if res_pm.returncode == 0 and "package:" in res_pm.stdout:
                    pm_ready = True
                    break

            time.sleep(3)

        if not boot_completed:
            raise ProofExecutionError(gate, "ANDROID_BOOT_FAILURE", f"sys.boot_completed != 1 within {timeout_seconds}s")
        if not pm_ready:
            raise ProofExecutionError(gate, "ANDROID_BOOT_FAILURE", "Package manager failed to respond to 'pm path android'")

        # Capture boot_id
        res_id = self._run_adb(["shell", "cat", "/proc/sys/kernel/random/boot_id"])
        if res_id.returncode != 0:
            raise ProofExecutionError(gate, "ANDROID_BOOT_FAILURE", f"Failed to read /proc/sys/kernel/random/boot_id: {res_id.stderr}")
        boot_id = res_id.stdout.strip()
        if not UUID_REGEX.match(boot_id):
            raise ProofExecutionError(gate, "ANDROID_BOOT_FAILURE", f"Captured boot_id is invalid format: '{boot_id}'")

        return boot_id

    # =========================================================================
    # Individual Proof Gates P1 through P10
    # =========================================================================

    def execute_p1(self) -> Dict[str, Any]:
        """P1: AVD CONFIG VALID"""
        t0 = datetime.now(timezone.utc).isoformat()
        try:
            res = self.avd_manager.verify_p1()
            res["start_time_utc"] = t0
            res["end_time_utc"] = datetime.now(timezone.utc).isoformat()
            self.results["P1"] = res
            return res
        except AvdInspectionError as err:
            raise ProofExecutionError("P1", "AVD_CONFIG_FAILURE", str(err)) from err

    def execute_p2(self) -> Dict[str, Any]:
        """P2: EMULATOR PROCESS STARTED"""
        t0 = datetime.now(timezone.utc).isoformat()
        if not self.emulator_bin.is_file():
            raise ProofExecutionError("P2", "ENVIRONMENT_FAILURE", f"Emulator binary missing: {self.emulator_bin}")

        try:
            self.active_process = self._start_emulator_process(no_snapshot=True, wipe_data=False)
            pid = self.active_process.pid
            time.sleep(1)
            # Check if process is still running
            poll = self.active_process.poll()
            if poll is not None:
                stderr = self.active_process.stderr.read() if self.active_process.stderr else ""
                raise ProofExecutionError("P2", "EMULATOR_START_FAILURE", f"Process exited immediately with code {poll}: {stderr}")

            res = {
                "gate": "P2",
                "result": "PASS",
                "emulator_binary": str(self.emulator_bin),
                "pid": pid,
                "start_time_utc": t0,
                "end_time_utc": datetime.now(timezone.utc).isoformat(),
            }
            self.results["P2"] = res
            return res
        except Exception as err:
            if isinstance(err, ProofExecutionError):
                raise
            raise ProofExecutionError("P2", "EMULATOR_START_FAILURE", str(err)) from err

    def execute_p3(self) -> Dict[str, Any]:
        """P3: PROCESS REMAINS ALIVE THROUGH STARTUP WINDOW"""
        t0 = datetime.now(timezone.utc).isoformat()
        if not self.active_process:
            raise ProofExecutionError("P3", "EMULATOR_START_FAILURE", "No active emulator process from P2")

        # Monitor process over startup_window_seconds
        interval = 2.0
        elapsed = 0.0
        while elapsed < self.startup_window_seconds:
            poll = self.active_process.poll()
            if poll is not None:
                stderr = self.active_process.stderr.read() if self.active_process.stderr else ""
                raise ProofExecutionError(
                    "P3",
                    "EMULATOR_START_FAILURE",
                    f"Emulator died during startup window at {elapsed:.1f}s with code {poll}: {stderr}",
                )
            time.sleep(interval)
            elapsed += interval

        res = {
            "gate": "P3",
            "result": "PASS",
            "monitored_window_seconds": self.startup_window_seconds,
            "pid": self.active_process.pid,
            "start_time_utc": t0,
            "end_time_utc": datetime.now(timezone.utc).isoformat(),
        }
        self.results["P3"] = res
        return res

    def execute_p4(self) -> Dict[str, Any]:
        """P4: ADB TRANSPORT ESTABLISHED"""
        t0 = datetime.now(timezone.utc).isoformat()
        try:
            self.device_serial = self._find_active_serial(timeout_seconds=60)
            res = {
                "gate": "P4",
                "result": "PASS",
                "device_serial": self.device_serial,
                "start_time_utc": t0,
                "end_time_utc": datetime.now(timezone.utc).isoformat(),
            }
            self.results["P4"] = res
            return res
        except Exception as err:
            if isinstance(err, ProofExecutionError):
                raise
            raise ProofExecutionError("P4", "ADB_TRANSPORT_FAILURE", str(err)) from err

    def execute_p5(self) -> Dict[str, Any]:
        """P5: ANDROID BOOT READY"""
        t0 = datetime.now(timezone.utc).isoformat()
        try:
            self.boot_id_p5 = self._wait_for_boot_completed(timeout_seconds=self.timeout_boot_seconds)
            res = {
                "gate": "P5",
                "result": "PASS",
                "device_serial": self.device_serial,
                "sys_boot_completed": "1",
                "package_manager_responsive": True,
                "boot_id": self.boot_id_p5,
                "start_time_utc": t0,
                "end_time_utc": datetime.now(timezone.utc).isoformat(),
            }
            self.results["P5"] = res
            return res
        except Exception as err:
            if isinstance(err, ProofExecutionError):
                raise
            raise ProofExecutionError("P5", "ANDROID_BOOT_FAILURE", str(err)) from err

    def execute_p6(self) -> Dict[str, Any]:
        """P6: STATIC TEST FIXTURE BUILDS AGAINST API 36"""
        t0 = datetime.now(timezone.utc).isoformat()
        try:
            apk_path = self.output_dir / "alvorada-harness.apk"
            self.built_apk_path = self.fixture_builder.build_apk(output_apk=apk_path)
            res = self.fixture_builder.verify_p6(self.built_apk_path)
            res["start_time_utc"] = t0
            res["end_time_utc"] = datetime.now(timezone.utc).isoformat()
            self.results["P6"] = res
            return res
        except FixtureBuildError as err:
            raise ProofExecutionError("P6", "APK_BUILD_FAILURE", str(err)) from err

    def execute_p7(self) -> Dict[str, Any]:
        """P7: APK INSTALLS"""
        t0 = datetime.now(timezone.utc).isoformat()
        if not self.built_apk_path or not self.built_apk_path.is_file():
            raise ProofExecutionError("P7", "APK_INSTALL_FAILURE", "No built APK available from P6")
        if not self.device_serial:
            raise ProofExecutionError("P7", "ADB_TRANSPORT_FAILURE", "No ADB serial available")

        # Execute adb install -r
        install_res = self._run_adb(["install", "-r", str(self.built_apk_path)], timeout=60)
        if install_res.returncode != 0 or "Success" not in install_res.stdout:
            raise ProofExecutionError(
                "P7",
                "APK_INSTALL_FAILURE",
                f"adb install failed (code {install_res.returncode}): {install_res.stdout} {install_res.stderr}",
            )

        # Confirm package presence via Package Manager
        pm_res = self._run_adb(["shell", "pm", "path", FIXTURE_PACKAGE_NAME])
        if pm_res.returncode != 0 or "package:" not in pm_res.stdout:
            raise ProofExecutionError(
                "P7",
                "APK_INSTALL_FAILURE",
                f"Package {FIXTURE_PACKAGE_NAME} not found via pm path after install: {pm_res.stderr}",
            )

        installed_path = pm_res.stdout.strip().replace("package:", "")
        res = {
            "gate": "P7",
            "result": "PASS",
            "package_name": FIXTURE_PACKAGE_NAME,
            "installed_apk_path": installed_path,
            "start_time_utc": t0,
            "end_time_utc": datetime.now(timezone.utc).isoformat(),
        }
        self.results["P7"] = res
        return res

    def execute_p8(self) -> Dict[str, Any]:
        """P8: PACKAGE EXECUTES / BASIC CONTROL PATH WORKS"""
        t0 = datetime.now(timezone.utc).isoformat()
        if not self.device_serial:
            raise ProofExecutionError("P8", "ADB_TRANSPORT_FAILURE", "No ADB serial available")

        # Send broadcast to HarnessReceiver
        bcast_action = "org.alvorada.reliability.harness.PING"
        bcast_component = f"{FIXTURE_PACKAGE_NAME}/.HarnessReceiver"
        cmd = ["shell", "am", "broadcast", "-a", bcast_action, "-n", bcast_component]
        bcast_res = self._run_adb(cmd, timeout=30)

        stdout = bcast_res.stdout
        # Expect result=42 and data="ALVORADA_P8_PASS" or broadcast completed
        if bcast_res.returncode != 0 or "result=42" not in stdout or "ALVORADA_P8_PASS" not in stdout:
            raise ProofExecutionError(
                "P8",
                "CODE_FAILURE",
                f"Harness receiver broadcast failed or returned unexpected data: {stdout} {bcast_res.stderr}",
            )

        # Also launch activity
        act_component = f"{FIXTURE_PACKAGE_NAME}/.HarnessActivity"
        act_res = self._run_adb(["shell", "am", "start", "-n", act_component], timeout=30)
        if act_res.returncode != 0:
            raise ProofExecutionError("P8", "CODE_FAILURE", f"Harness activity launch failed: {act_res.stderr}")

        res = {
            "gate": "P8",
            "result": "PASS",
            "package_name": FIXTURE_PACKAGE_NAME,
            "broadcast_action": bcast_action,
            "broadcast_response": "result=42, data=\"ALVORADA_P8_PASS\"",
            "activity_component": act_component,
            "start_time_utc": t0,
            "end_time_utc": datetime.now(timezone.utc).isoformat(),
        }
        self.results["P8"] = res
        return res

    def execute_p9(self) -> Dict[str, Any]:
        """P9: TRUE COLD RESTART PERSISTENCE"""
        t0 = datetime.now(timezone.utc).isoformat()
        if not self.active_process:
            raise ProofExecutionError("P9", "PERSISTENCE_FAILURE", "No running emulator process to restart")

        # 1. Terminate current emulator process
        self._stop_emulator_process()
        time.sleep(3)

        # 2. Start a NEW emulator process (same AVD, NO snapshot, NO wipe-data)
        self.active_process = self._start_emulator_process(no_snapshot=True, wipe_data=False)
        time.sleep(2)
        if self.active_process.poll() is not None:
            raise ProofExecutionError("P9", "EMULATOR_START_FAILURE", "New emulator process exited immediately during cold restart")

        # 3. Wait for ADB transport and boot completed
        self.device_serial = self._find_active_serial(timeout_seconds=60)
        self.boot_id_p9 = self._wait_for_boot_completed(gate="P9", timeout_seconds=self.timeout_boot_seconds)

        # 4. Strict assertion: boot_id must change
        if self.boot_id_p9 == self.boot_id_p5:
            raise ProofExecutionError(
                "P9",
                "PERSISTENCE_FAILURE",
                f"boot_id did not change across cold restart! (p5={self.boot_id_p5}, p9={self.boot_id_p9})",
            )

        # 5. Strict assertion: test package must remain installed
        pm_res = self._run_adb(["shell", "pm", "path", FIXTURE_PACKAGE_NAME])
        if pm_res.returncode != 0 or "package:" not in pm_res.stdout:
            raise ProofExecutionError(
                "P9",
                "PERSISTENCE_FAILURE",
                f"Test package {FIXTURE_PACKAGE_NAME} was lost across cold restart: {pm_res.stderr}",
            )

        res = {
            "gate": "P9",
            "result": "PASS",
            "semantics": "COLD_RESTART_WITHOUT_SNAPSHOT_OR_WIPE",
            "boot_id_initial": self.boot_id_p5,
            "boot_id_cold_restart": self.boot_id_p9,
            "boot_id_changed": True,
            "package_persisted": True,
            "start_time_utc": t0,
            "end_time_utc": datetime.now(timezone.utc).isoformat(),
        }
        self.results["P9"] = res
        return res

    def execute_p10(self) -> Dict[str, Any]:
        """P10: CONTROLLED GUEST REBOOT"""
        t0 = datetime.now(timezone.utc).isoformat()
        if not self.device_serial:
            raise ProofExecutionError("P10", "ADB_TRANSPORT_FAILURE", "No ADB serial available")

        # 1. Trigger guest reboot
        reboot_res = self._run_adb(["reboot"], timeout=20)
        if reboot_res.returncode != 0:
            raise ProofExecutionError("P10", "REBOOT_FAILURE", f"adb reboot failed: {reboot_res.stderr}")

        # 2. Wait for device to disconnect
        time.sleep(5)

        # 3. Wait for ADB recovery and boot completed
        self.device_serial = self._find_active_serial(timeout_seconds=60)
        self.boot_id_p10 = self._wait_for_boot_completed(gate="P10", timeout_seconds=self.timeout_boot_seconds)

        # 4. Strict assertions: boot_id must be fresh
        if self.boot_id_p10 == self.boot_id_p9 or self.boot_id_p10 == self.boot_id_p5:
            raise ProofExecutionError(
                "P10",
                "REBOOT_FAILURE",
                f"boot_id did not change across guest reboot! (p10={self.boot_id_p10}, p9={self.boot_id_p9}, p5={self.boot_id_p5})",
            )

        # 5. Strict assertion: test package must remain installed
        pm_res = self._run_adb(["shell", "pm", "path", FIXTURE_PACKAGE_NAME])
        if pm_res.returncode != 0 or "package:" not in pm_res.stdout:
            raise ProofExecutionError(
                "P10",
                "REBOOT_FAILURE",
                f"Test package {FIXTURE_PACKAGE_NAME} was lost across guest reboot: {pm_res.stderr}",
            )

        # 6. Cleanly terminate emulator process at campaign completion
        self._stop_emulator_process()

        res = {
            "gate": "P10",
            "result": "PASS",
            "semantics": "CONTROLLED_GUEST_REBOOT",
            "boot_id_initial": self.boot_id_p5,
            "boot_id_cold_restart": self.boot_id_p9,
            "boot_id_guest_reboot": self.boot_id_p10,
            "boot_id_changed": True,
            "package_persisted": True,
            "adb_recovered": True,
            "start_time_utc": t0,
            "end_time_utc": datetime.now(timezone.utc).isoformat(),
        }
        self.results["P10"] = res
        return res

    # =========================================================================
    # Full Sequence Orchestrator & Evidence Generation
    # =========================================================================

    def run_all_proofs(self) -> Dict[str, Any]:
        """Execute P1 through P10 sequentially and generate canonical evidence."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        overall_status = "PASS"
        failure_record: Optional[Dict[str, Any]] = None

        sequence = [
            ("P1", self.execute_p1),
            ("P2", self.execute_p2),
            ("P3", self.execute_p3),
            ("P4", self.execute_p4),
            ("P5", self.execute_p5),
            ("P6", self.execute_p6),
            ("P7", self.execute_p7),
            ("P8", self.execute_p8),
            ("P9", self.execute_p9),
            ("P10", self.execute_p10),
        ]

        try:
            for gate_name, gate_fn in sequence:
                print(f"--> EXECUTING {gate_name}...", flush=True)
                res = gate_fn()
                self.results[gate_name] = res
                print(f"    {gate_name} RESULT: {res.get('result')}", flush=True)

        except ProofExecutionError as p_err:
            overall_status = "FAIL"
            failure_record = {
                "gate": p_err.gate,
                "classification": p_err.classification,
                "reason": p_err.reason,
            }
            print(f"!!! PROOF SEQUENCE FAILED AT {p_err.gate}: {p_err.reason}", file=sys.stderr)
        except Exception as err:
            overall_status = "FAIL"
            failure_record = {
                "gate": "UNKNOWN",
                "classification": "UNKNOWN_INSUFFICIENT_EVIDENCE",
                "reason": str(err),
            }
            print(f"!!! UNHANDLED EXCEPTION DURING PROOF SEQUENCE: {err}", file=sys.stderr)
        finally:
            self._stop_emulator_process()

        # Build comprehensive report
        report = {
            "contract": CONTRACT_PROOF_SEQUENCE,
            "campaign": "ALVORADA_G1_POST_FOUNDER_APPROVAL_001",
            "overall_status": overall_status,
            "repository_commit_sha": self.repo_sha,
            "ci_run_id": self.run_id,
            "avd_name": self.avd_name,
            "system_image_package": LOCKED_SYSTEM_IMAGE_PACKAGE,
            "selected_gpu": LOCKED_GPU_MODE,
            "gates": self.results,
        }
        if failure_record:
            report["failure"] = failure_record

        # Write proof-report.json
        json_path = self.output_dir / "proof-report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=True)

        # Write proof-report.txt
        txt_path = self.output_dir / "proof-report.txt"
        self._write_human_report(txt_path, report)

        # Write checksums.sha256
        self._write_checksums(self.output_dir, [json_path, txt_path])

        if overall_status != "PASS":
            raise ProofExecutionError(
                failure_record.get("gate", "UNKNOWN"),
                failure_record.get("classification", "UNKNOWN_INSUFFICIENT_EVIDENCE"),
                failure_record.get("reason", "Unknown failure"),
            )

        return report

    def _write_human_report(self, path: Path, report: Dict[str, Any]) -> None:
        lines = [
            "ALVORADA G1 P1-P10 PROOF SEQUENCE REPORT",
            "========================================",
            f"Contract:                 {report['contract']}",
            f"Campaign:                 {report['campaign']}",
            f"Overall Status:           {report['overall_status']}",
            f"Repository Commit SHA:    {report['repository_commit_sha']}",
            f"CI Run ID:                {report['ci_run_id']}",
            f"AVD Name:                 {report['avd_name']}",
            f"System Image Package:     {report['system_image_package']}",
            f"Selected GPU Mode:        {report['selected_gpu']}",
            "",
            "GATE EXECUTION LEDGER",
            "---------------------",
        ]

        for gate in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"):
            info = report.get("gates", {}).get(gate)
            if info:
                lines.append(f"  [{gate}] {info.get('result', 'UNKNOWN')}")
                for k, v in info.items():
                    if k not in ("gate", "result"):
                        lines.append(f"       {k}: {v}")
            else:
                lines.append(f"  [{gate}] NOT_REACHED")

        if report.get("failure"):
            fail = report["failure"]
            lines.extend([
                "",
                "FAILURE ANALYSIS",
                "----------------",
                f"Failing Gate:   {fail.get('gate')}",
                f"Classification: {fail.get('classification')}",
                f"Reason:         {fail.get('reason')}",
            ])

        lines.extend([
            "",
            f"SCIENTIFIC VERDICT: {report['overall_status']}",
            "END OF REPORT",
            "",
        ])

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _write_checksums(self, directory: Path, files: List[Path]) -> None:
        lines: List[str] = []
        for p in files:
            sha = hashlib.sha256()
            with open(p, "rb") as f:
                while chunk := f.read(65536):
                    sha.update(chunk)
            lines.append(f"{sha.hexdigest()}  {p.name}")
        chk_path = directory / "checksums.sha256"
        with open(chk_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="ALVORADA P1-P10 Proof Runner")
    parser.add_argument("--sdk-root", type=Path, default=None)
    parser.add_argument("--avd-name", type=str, default=AVD_NAME_DEFAULT)
    parser.add_argument("--repo-sha", type=str, default="")
    parser.add_argument("--run-id", type=str, default="")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--timeout-boot", type=int, default=240)
    parser.add_argument("--startup-window", type=int, default=15)
    args = parser.parse_args()

    runner = ProofRunner(
        sdk_root=args.sdk_root,
        avd_name=args.avd_name,
        repo_sha=args.repo_sha,
        run_id=args.run_id,
        output_dir=args.output_dir,
        timeout_boot_seconds=args.timeout_boot,
        startup_window_seconds=args.startup_window,
    )
    runner.run_all_proofs()


if __name__ == "__main__":
    main()
