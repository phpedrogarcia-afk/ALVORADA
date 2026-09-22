from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional, Tuple
import unittest
from unittest.mock import MagicMock, patch

from wave2_avd_manager import (
    AVD_NAME_DEFAULT,
    LOCKED_GPU_MODE,
    LOCKED_SYSTEM_IMAGE_PACKAGE,
    Wave2AvdManager,
    AvdInspectionError,
    parse_ini_file,
    write_ini_file,
)


class TestWave2AvdManager(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.sdk_root = self.root / "sdk"
        self.avd_home = self.root / "avd_home"
        self.sdk_root.mkdir(parents=True, exist_ok=True)
        self.avd_home.mkdir(parents=True, exist_ok=True)

        # Setup mock system image directory in sdk
        self.sys_img_dir = self.sdk_root / "system-images" / "android-36" / "default" / "x86_64"
        self.sys_img_dir.mkdir(parents=True, exist_ok=True)
        (self.sys_img_dir / "system.img").write_text("mock_system_img")

        self.mgr = Wave2AvdManager(sdk_root=self.sdk_root, avd_home=self.avd_home)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_parse_and_write_ini(self) -> None:
        ini_file = self.root / "test.ini"
        write_ini_file(ini_file, {"foo": "bar", "num": "42"})
        parsed = parse_ini_file(ini_file)
        self.assertEqual(parsed["foo"], "bar")
        self.assertEqual(parsed["num"], "42")

    def test_inspect_existing_avd_absent(self) -> None:
        status, config, reason = self.mgr.inspect_existing_avd()
        self.assertEqual(status, "ABSENT")
        self.assertIsNone(config)
        self.assertIn("does not exist", reason)

    def test_inspect_existing_avd_mismatch_sysdir(self) -> None:
        desc = self.avd_home / f"{AVD_NAME_DEFAULT}.ini"
        avd_dir = self.avd_home / f"{AVD_NAME_DEFAULT}.avd"
        avd_dir.mkdir(parents=True, exist_ok=True)
        desc.write_text(f"path={avd_dir}\n")

        config_file = avd_dir / "config.ini"
        write_ini_file(
            config_file,
            {
                "image.sysdir.1": "system-images/android-34/google_apis/x86_64",
                "abi.type": "x86_64",
            },
        )

        status, config, reason = self.mgr.inspect_existing_avd()
        self.assertEqual(status, "MISMATCH")
        self.assertIn("does not contain expected", reason)

    def test_inspect_existing_avd_matching(self) -> None:
        desc = self.avd_home / f"{AVD_NAME_DEFAULT}.ini"
        avd_dir = self.avd_home / f"{AVD_NAME_DEFAULT}.avd"
        avd_dir.mkdir(parents=True, exist_ok=True)
        desc.write_text(f"path={avd_dir}\n")

        config_file = avd_dir / "config.ini"
        write_ini_file(
            config_file,
            {
                "image.sysdir.1": "system-images/android-36/default/x86_64",
                "abi.type": "x86_64",
            },
        )

        status, config, reason = self.mgr.inspect_existing_avd()
        self.assertEqual(status, "MATCH")
        self.assertIsNone(reason)

    def test_configure_hardware_ini(self) -> None:
        desc = self.avd_home / f"{AVD_NAME_DEFAULT}.ini"
        avd_dir = self.avd_home / f"{AVD_NAME_DEFAULT}.avd"
        avd_dir.mkdir(parents=True, exist_ok=True)
        desc.write_text(f"path={avd_dir}\n")

        config_file = avd_dir / "config.ini"
        config_file.write_text("image.sysdir.1=system-images/android-36/default/x86_64\n")

        self.mgr.configure_hardware_ini()
        parsed = parse_ini_file(config_file)
        self.assertEqual(parsed["hw.cpu.ncore"], "2")
        self.assertEqual(parsed["hw.ramSize"], "2048")
        self.assertEqual(parsed["hw.gpu.mode"], LOCKED_GPU_MODE)
        self.assertEqual(parsed["hw.gpu.enabled"], "yes")
        self.assertEqual(parsed["fastboot.forceColdBoot"], "yes")

    def test_verify_p1_success(self) -> None:
        desc = self.avd_home / f"{AVD_NAME_DEFAULT}.ini"
        avd_dir = self.avd_home / f"{AVD_NAME_DEFAULT}.avd"
        avd_dir.mkdir(parents=True, exist_ok=True)
        desc.write_text(f"path={avd_dir}\n")

        config_file = avd_dir / "config.ini"
        write_ini_file(
            config_file,
            {
                "image.sysdir.1": "system-images/android-36/default/x86_64",
                "abi.type": "x86_64",
                "hw.cpu.ncore": "2",
                "hw.ramSize": "2048",
                "hw.gpu.mode": "swiftshader",
                "hw.gpu.enabled": "yes",
            },
        )

        res = self.mgr.verify_p1()
        self.assertEqual(res["gate"], "P1")
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["cpu_cores"], 2)
        self.assertEqual(res["ram_mb"], 2048)
        self.assertEqual(res["gpu_mode"], "swiftshader")

    def test_verify_p1_fails_on_cpu_less_than_2(self) -> None:
        desc = self.avd_home / f"{AVD_NAME_DEFAULT}.ini"
        avd_dir = self.avd_home / f"{AVD_NAME_DEFAULT}.avd"
        avd_dir.mkdir(parents=True, exist_ok=True)
        desc.write_text(f"path={avd_dir}\n")

        config_file = avd_dir / "config.ini"
        write_ini_file(
            config_file,
            {
                "image.sysdir.1": "system-images/android-36/default/x86_64",
                "abi.type": "x86_64",
                "hw.cpu.ncore": "1",
                "hw.ramSize": "2048",
                "hw.gpu.mode": "swiftshader",
                "hw.gpu.enabled": "yes",
            },
        )

        with self.assertRaises(AvdInspectionError) as ctx:
            self.mgr.verify_p1()
        self.assertIn("hw.cpu.ncore (1) is less than locked", str(ctx.exception))

    def test_verify_p1_fails_on_gpu_mode_mismatch(self) -> None:
        desc = self.avd_home / f"{AVD_NAME_DEFAULT}.ini"
        avd_dir = self.avd_home / f"{AVD_NAME_DEFAULT}.avd"
        avd_dir.mkdir(parents=True, exist_ok=True)
        desc.write_text(f"path={avd_dir}\n")

        config_file = avd_dir / "config.ini"
        write_ini_file(
            config_file,
            {
                "image.sysdir.1": "system-images/android-36/default/x86_64",
                "abi.type": "x86_64",
                "hw.cpu.ncore": "2",
                "hw.ramSize": "2048",
                "hw.gpu.mode": "host",
                "hw.gpu.enabled": "yes",
            },
        )

        with self.assertRaises(AvdInspectionError) as ctx:
            self.mgr.verify_p1()
        self.assertIn("hw.gpu.mode ('host') does not match locked", str(ctx.exception))

    def test_create_avd_reuses_matching(self) -> None:
        desc = self.avd_home / f"{AVD_NAME_DEFAULT}.ini"
        avd_dir = self.avd_home / f"{AVD_NAME_DEFAULT}.avd"
        avd_dir.mkdir(parents=True, exist_ok=True)
        desc.write_text(f"path={avd_dir}\n")

        config_file = avd_dir / "config.ini"
        write_ini_file(
            config_file,
            {
                "image.sysdir.1": "system-images/android-36/default/x86_64",
                "abi.type": "x86_64",
            },
        )

        res = self.mgr.create_avd(force_recreate=False)
        self.assertEqual(res["action"], "REUSED_EXISTING")

    @patch("subprocess.run")
    def test_create_avd_calls_avdmanager_when_absent(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"OK", stderr=b"")

        # Fake creation directory side effect
        def side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            desc = self.avd_home / f"{AVD_NAME_DEFAULT}.ini"
            avd_dir = self.avd_home / f"{AVD_NAME_DEFAULT}.avd"
            avd_dir.mkdir(parents=True, exist_ok=True)
            desc.write_text(f"path={avd_dir}\n")
            (avd_dir / "config.ini").write_text("image.sysdir.1=system-images/android-36/default/x86_64\n")
            return MagicMock(returncode=0, stdout=b"Created", stderr=b"")

        mock_run.side_effect = side_effect
        res = self.mgr.create_avd(force_recreate=True)
        self.assertEqual(res["action"], "CREATED_NEW")
        mock_run.assert_called()


if __name__ == "__main__":
    unittest.main()
