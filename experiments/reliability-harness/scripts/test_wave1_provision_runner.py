#!/usr/bin/env python3
"""
ALVORADA — Unit Test Suite for Wave 1 Provisioning Runner
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
from proposal_assembly_runner import verify_directory_checksums
from wave1_provision_runner import (
    ALLOWED_LOCKED_PACKAGES,
    CONTRACT_WAVE1_ENVIRONMENT,
    CONTRACT_WAVE1_PROVENANCE,
    execute_sdkmanager_install,
    inspect_package_state,
    run_wave1_provisioning,
)


class TestWave1ProvisionRunner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sdk_dir = os.path.join(self.temp_dir, "android_sdk")
        self.out_dir = os.path.join(self.temp_dir, "wave1_out")
        os.makedirs(self.sdk_dir, exist_ok=True)

        # Mock lock file
        self.lock_path = os.path.join(self.temp_dir, "lock.json")
        self.lock_data = {
            "catalog_digest": "e9148d7bcdb5124182f87787a78899845aa9a60aefbe5c4bc581539201b4f6ed",
            "contract": "ALVORADA_LOCK_PAYLOAD_V1",
            "environment_locks": {
                "emulator_revision": "37.1.11",
                "jdk_major": 17,
            },
            "hard_locks": [
                {"package_path": "build-tools;36.0.0", "revision": "36.0.0"},
                {"package_path": "emulator", "revision": "37.1.11"},
                {"package_path": "platform-tools", "revision": "37.0.1"},
                {"package_path": "platforms;android-36", "revision": "2"},
                {"package_path": "system-images;android-36;default;x86_64", "revision": "2"},
            ],
            "proposal_digest": "5517290ec9b90cdcbc13ad34a1228a1ff422f2a5c2326d622e9f2ae249b411b4",
            "selected_gpu": "swiftshader",
        }
        with open(self.lock_path, "wb") as f:
            f.write(canonicalize_json_v1(self.lock_data))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_mock_package(self, rel_path: str, revision: str, is_xml: bool = True):
        pkg_dir = os.path.join(self.sdk_dir, rel_path)
        os.makedirs(pkg_dir, exist_ok=True)
        props_file = os.path.join(pkg_dir, "source.properties")
        with open(props_file, "w", encoding="utf-8") as f:
            f.write(f"Pkg.Revision={revision}\n")

        if is_xml:
            parts = revision.split(".")
            children = [f"<major>{parts[0]}</major>"]
            if len(parts) > 1:
                children.append(f"<minor>{parts[1]}</minor>")
            if len(parts) > 2:
                children.append(f"<micro>{parts[2]}</micro>")
            child_str = "\n    ".join(children)
            xml_file = os.path.join(pkg_dir, "package.xml")
            xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<ns2:repository xmlns:ns2="http://schemas.android.com/repository/android/common/02">
  <revision>
    {child_str}
  </revision>
</ns2:repository>"""
            with open(xml_file, "w", encoding="utf-8") as f:
                f.write(xml_content)

    def test_inspect_package_state_absent(self):
        state = inspect_package_state(self.sdk_dir, "emulator", "37.1.11")
        self.assertEqual(state["state"], "ABSENT")
        self.assertIsNone(state["installed_revision"])

    def test_inspect_package_state_matching(self):
        self._create_mock_package("emulator", "37.1.11")
        state = inspect_package_state(self.sdk_dir, "emulator", "37.1.11")
        self.assertEqual(state["state"], "PRESENT_MATCHING_LOCK")
        self.assertEqual(state["installed_revision"], "37.1.11")

    def test_inspect_package_state_different_revision(self):
        self._create_mock_package("emulator", "36.0.0")
        state = inspect_package_state(self.sdk_dir, "emulator", "37.1.11")
        self.assertEqual(state["state"], "PRESENT_DIFFERENT_REVISION")
        self.assertEqual(state["installed_revision"], "36.0.0")

    def test_inspect_package_state_corrupt(self):
        pkg_dir = os.path.join(self.sdk_dir, "emulator")
        os.makedirs(pkg_dir, exist_ok=True)
        # Empty directory without metadata
        state = inspect_package_state(self.sdk_dir, "emulator", "37.1.11")
        self.assertEqual(state["state"], "PARTIAL_OR_CORRUPT")

    def test_execute_sdkmanager_install_unauthorized_package_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            execute_sdkmanager_install(
                sdkmanager_path="/bin/fake",
                sdk_root=self.sdk_dir,
                packages_to_install=["ndk;27.0.12077973"],
            )
        self.assertIn("UNAUTHORIZED_PACKAGE_INSTALLATION_ATTEMPT", str(ctx.exception))

    def test_run_wave1_provisioning_all_matching_dry_run(self):
        # Create all 5 mock packages
        self._create_mock_package(os.path.join("build-tools", "36.0.0"), "36.0.0")
        self._create_mock_package("emulator", "37.1.11")
        # Create fake emulator executable
        emu_bin = os.path.join(self.sdk_dir, "emulator", "emulator")
        with open(emu_bin, "w") as f:
            f.write("#!/bin/sh\necho ok\n")
        self._create_mock_package("platform-tools", "37.0.1")
        self._create_mock_package(os.path.join("platforms", "android-36"), "2")
        self._create_mock_package(os.path.join("system-images", "android-36", "default", "x86_64"), "2")

        # Create mock cmdline-tools/latest/bin/sdkmanager
        sdkm_bin = os.path.join(self.sdk_dir, "cmdline-tools", "latest", "bin", "sdkmanager")
        os.makedirs(os.path.dirname(sdkm_bin), exist_ok=True)
        with open(sdkm_bin, "w") as f:
            f.write("#!/bin/sh\n")

        env_payload, prov_payload, out_dir = run_wave1_provisioning(
            lock_file=self.lock_path,
            output_dir=self.out_dir,
            repo_sha="1111111111111111111111111111111111111111",
            run_id="999",
            observed_at="2026-09-22T15:00:00Z",
            sdk_root_override=self.sdk_dir,
            dry_run=True,
        )

        self.assertEqual(env_payload["contract"], CONTRACT_WAVE1_ENVIRONMENT)
        self.assertTrue(env_payload["locked_environment_match"])
        self.assertEqual(env_payload["lock_digest"], "ac243a03caca0333eec85721cbd27f828a001c3b19ed80d7994e33589f065f05")
        self.assertEqual(prov_payload["contract"], CONTRACT_WAVE1_PROVENANCE)
        self.assertEqual(len(env_payload["packages"]), 5)

        verify_directory_checksums(self.out_dir, required=True)

        # Check evidence report
        txt_file = os.path.join(self.out_dir, "wave1-evidence.txt")
        with open(txt_file, "r", encoding="utf-8") as f:
            txt = f.read()
        self.assertIn("LOCKED_ENVIRONMENT_MATCH = TRUE", txt)
        self.assertIn("WAVE 1 SCIENTIFIC VERDICT: PASS", txt)


if __name__ == "__main__":
    unittest.main()
