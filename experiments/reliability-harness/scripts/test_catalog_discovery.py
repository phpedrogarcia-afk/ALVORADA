#!/usr/bin/env python3
"""
Unit tests for ALVORADA Catalog Discovery Engine and Static Policy Verifier
"""

import os
import sys
import json
import subprocess
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog_discovery import (
    canonicalize_json_v1,
    hash_canonical_json_v1,
    CatalogParser,
    StaticPolicyVerifier,
    Wave1PreflightVerifier,
    Wave2AvdConfigurator,
    PACKAGE_STATE_ABSENT,
    PACKAGE_STATE_PRESENT_MATCHING,
    PACKAGE_STATE_PRESENT_DIFFERENT,
    PACKAGE_STATE_CATALOG_MISSING,
    PACKAGE_STATE_METADATA_AMBIGUOUS,
)

SAMPLE_VALID_SDKMANAGER_OUTPUT = """
Installed packages:
--------------------------------------
emulator
  Description:        Android Emulator
  Version:            37.1.11
  Installed Location: /usr/local/lib/android/sdk/emulator

Available Packages:
--------------------------------------
emulator
  Description:        Android Emulator
  Version:            37.1.11

platform-tools
  Description:        Android SDK Platform-Tools
  Version:            36.0.0

platforms;android-36
  Description:        Android SDK Platform 36
  Version:            1

build-tools;36.0.0
  Description:        Android SDK Build-Tools 36.0.0
  Version:            36.0.0

system-images;android-36;default;x86_64
  Description:        ARM 64 v8a System Image
  Version:            2
"""

SAMPLE_DIFFERENT_REVISION_OUTPUT = """
Installed packages:
--------------------------------------
emulator
  Description:        Android Emulator
  Version:            35.0.0
  Installed Location: /usr/local/lib/android/sdk/emulator

Available Packages:
--------------------------------------
emulator
  Description:        Android Emulator
  Version:            37.1.11

platform-tools
  Description:        Android SDK Platform-Tools
  Version:            36.0.0

platforms;android-36
  Description:        Android SDK Platform 36
  Version:            1

build-tools;36.0.0
  Description:        Android SDK Build-Tools 36.0.0
  Version:            36.0.0

system-images;android-36;default;x86_64
  Description:        ARM 64 v8a System Image
  Version:            2
"""

SAMPLE_DUPLICATE_OUTPUT = """
Available Packages:
--------------------------------------
emulator
  Description:        Android Emulator
  Version:            37.1.11

emulator
  Description:        Android Emulator Duplicate
  Version:            37.1.12
"""


class TestCanonicalJsonV1(unittest.TestCase):
    def test_key_sorting_determinism(self):
        obj1 = {"z": 1, "a": {"d": 4, "b": 2}, "m": [3, 2, 1]}
        obj2 = {"a": {"b": 2, "d": 4}, "m": [3, 2, 1], "z": 1}

        b1 = canonicalize_json_v1(obj1)
        b2 = canonicalize_json_v1(obj2)

        self.assertEqual(b1, b2)
        self.assertEqual(b1, b'{"a":{"b":2,"d":4},"m":[3,2,1],"z":1}')
        self.assertEqual(hash_canonical_json_v1(obj1), hash_canonical_json_v1(obj2))

    def test_compact_no_whitespace(self):
        obj = {"key": "value", "list": [1, 2]}
        raw = canonicalize_json_v1(obj)
        self.assertNotIn(b" ", raw)
        self.assertNotIn(b"\n", raw)


class TestCatalogParser(unittest.TestCase):
    def test_valid_parsing(self):
        parser = CatalogParser(SAMPLE_VALID_SDKMANAGER_OUTPUT)
        proposal = parser.parse()

        self.assertTrue(proposal["ready_for_human_review"])
        self.assertEqual(proposal["lock_approved"], "NO")

        # emulator was both installed and available with matching 37.1.11
        em = proposal["packages"]["emulator"]
        self.assertEqual(em["state"], PACKAGE_STATE_PRESENT_MATCHING)
        self.assertEqual(em["catalog_revision"], "37.1.11")
        self.assertEqual(em["installed_revision"], "37.1.11")

        # platform-tools was only in available
        pt = proposal["packages"]["platform-tools"]
        self.assertEqual(pt["state"], PACKAGE_STATE_ABSENT)
        self.assertEqual(pt["catalog_revision"], "36.0.0")
        self.assertIsNone(pt["installed_revision"])

    def test_different_revision_parsing(self):
        parser = CatalogParser(SAMPLE_DIFFERENT_REVISION_OUTPUT)
        proposal = parser.parse()

        self.assertTrue(proposal["ready_for_human_review"])
        em = proposal["packages"]["emulator"]
        self.assertEqual(em["state"], PACKAGE_STATE_PRESENT_DIFFERENT)
        self.assertEqual(em["catalog_revision"], "37.1.11")
        self.assertEqual(em["installed_revision"], "35.0.0")

    def test_duplicate_ambiguity(self):
        parser = CatalogParser(SAMPLE_DUPLICATE_OUTPUT)
        proposal = parser.parse()

        self.assertFalse(proposal["ready_for_human_review"])
        em = proposal["packages"]["emulator"]
        self.assertEqual(em["state"], PACKAGE_STATE_METADATA_AMBIGUOUS)

    def test_missing_packages(self):
        parser = CatalogParser("Available Packages:\n--------------------------------------\n")
        proposal = parser.parse()

        self.assertFalse(proposal["ready_for_human_review"])
        for pkg in proposal["packages"].values():
            self.assertEqual(pkg["state"], PACKAGE_STATE_CATALOG_MISSING)


class TestStaticPolicyVerifier(unittest.TestCase):
    def setUp(self):
        self.verifier = StaticPolicyVerifier()

    def test_prohibited_scripts(self):
        bad_scripts = [
            "sdkmanager --licenses",
            "sdkmanager --install 'platforms;android-36'",
            "sdkmanager --update",
            "avdmanager create avd -n test",
            "adb install app.apk",
            "emulator -avd test_avd",
            "chmod 777 /dev/kvm",
            "yes | sdkmanager --licenses",
        ]
        for script in bad_scripts:
            ok, violations = self.verifier.verify_script(script)
            self.assertFalse(ok, f"Expected violation for: {script}")
            self.assertGreater(len(violations), 0)

    def test_allowed_script(self):
        good_script = 'sdkmanager --sdk_root="$CANONICAL_SDK_ROOT" --list --verbose --channel=0'
        ok, violations = self.verifier.verify_script(good_script)
        self.assertTrue(ok)
        self.assertEqual(len(violations), 0)

    def test_emulator_allowlist(self):
        # -help is unconditionally allowed
        ok, reason = self.verifier.verify_emulator_invocation(["-help"])
        self.assertTrue(ok)
        self.assertIsNone(reason)

        # -help-gpu is allowed ONLY if help proved it
        ok, reason = self.verifier.verify_emulator_invocation(["-help-gpu"], help_proved_gpu=False)
        self.assertFalse(ok)
        self.assertEqual(reason, "GPU_HELP_INTERFACE_NOT_PREVIOUSLY_PROVED")

        ok, reason = self.verifier.verify_emulator_invocation(["-help-gpu"], help_proved_gpu=True)
        self.assertTrue(ok)
        self.assertIsNone(reason)

        # All other args are strictly denied
        ok, reason = self.verifier.verify_emulator_invocation(["-gpu", "host"])
        self.assertFalse(ok)
        self.assertIn("UNAUTHORIZED_EMULATOR_ARGUMENTS", reason)


class TestCliIntegration(unittest.TestCase):
    def setUp(self):
        self.script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog_discovery.py")

    def test_cli_verify_script_valid(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sh") as tmp:
            tmp.write("#!/bin/bash\necho hello\n")
            tmp_path = tmp.name

        try:
            res = subprocess.run([sys.executable, self.script_path, "verify-script", tmp_path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("STATIC_POLICY_VERIFICATION=PASS", res.stdout)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_cli_verify_script_forbidden(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sh") as tmp:
            tmp.write("#!/bin/bash\nsdkmanager --licenses\n")
            tmp_path = tmp.name

        try:
            res = subprocess.run([sys.executable, self.script_path, "verify-script", tmp_path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 1)
            self.assertIn("STATIC_POLICY_VERIFICATION=FAIL", res.stdout)
            self.assertIn("VIOLATION=PROHIBITED_LICENSE_ACCEPTANCE", res.stdout)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_cli_parse_valid(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as in_tmp:
            in_tmp.write(SAMPLE_VALID_SDKMANAGER_OUTPUT)
            in_path = in_tmp.name

        out_path = in_path + ".proposal.json"
        try:
            res = subprocess.run(
                [sys.executable, self.script_path, "parse", "--input", in_path, "--output", out_path, "--repo-sha", "test-sha", "--run-id", "12345"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("PROPOSAL_SHA256=", res.stdout)
            self.assertIn("READY_FOR_HUMAN_REVIEW=YES", res.stdout)
            self.assertTrue(os.path.exists(out_path))
            with open(out_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["contract"], "ALVORADA_CATALOG_LOCK_PROPOSAL_V1")
            self.assertEqual(data["metadata"]["repo_sha"], "test-sha")
        finally:
            if os.path.exists(in_path):
                os.remove(in_path)
            if os.path.exists(out_path):
                os.remove(out_path)


class TestWave1PreflightVerifier(unittest.TestCase):
    def setUp(self):
        self.canonical_proposal_path = os.path.abspath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../..", "evidence/g1/raw-mission05r/canonical_catalog_proposal.json")
        )

    def test_canonical_proposal_preflight(self):
        verifier = Wave1PreflightVerifier(self.canonical_proposal_path)
        is_valid, plan, errors = verifier.verify_and_plan(enforce_approval=False)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        self.assertFalse(plan["lock_approved"])
        self.assertEqual(plan["proposal_sha256"], "55087ef875573c7204251cd22ddd5fa92dd35b98321d95bcf41e60bddcc50d9f")
        self.assertEqual(len(plan["required_installs"]), 2)
        pkgs = [item["package"] for item in plan["required_installs"]]
        self.assertIn("emulator", pkgs)
        self.assertIn("system-images;android-36;default;x86_64", pkgs)

    def test_enforce_approval_rejects_unapproved(self):
        verifier = Wave1PreflightVerifier(self.canonical_proposal_path)
        is_valid, plan, errors = verifier.verify_and_plan(enforce_approval=True)
        self.assertFalse(is_valid)
        self.assertIn("LOCK_NOT_APPROVED_BY_FOUNDER", errors)

    def test_tampered_hash_rejection(self):
        with open(self.canonical_proposal_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["proposal_sha256"] = "corrupted_sha256_hash_123456789"
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            verifier = Wave1PreflightVerifier(tmp_path)
            is_valid, plan, errors = verifier.verify_and_plan()
            self.assertFalse(is_valid)
            self.assertTrue(any("HASH_MISMATCH" in err for err in errors))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_approved_proposal_preserves_discovery_hash_and_executes(self):
        with open(self.canonical_proposal_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["lock_approved"] = "YES"
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            verifier = Wave1PreflightVerifier(tmp_path)
            is_valid, plan, errors = verifier.verify_and_plan(enforce_approval=True)
            self.assertTrue(is_valid, f"Expected valid plan, got errors: {errors}")
            self.assertEqual(len(errors), 0)
            self.assertTrue(plan["lock_approved"])
            self.assertTrue(plan["ready_for_execution"])
            self.assertEqual(plan["proposal_sha256"], "55087ef875573c7204251cd22ddd5fa92dd35b98321d95bcf41e60bddcc50d9f")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_tampered_package_revision_fails_even_if_approved(self):
        with open(self.canonical_proposal_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["lock_approved"] = "YES"
        data["packages"]["emulator"]["catalog_revision"] = "99.9.9"
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            verifier = Wave1PreflightVerifier(tmp_path)
            is_valid, plan, errors = verifier.verify_and_plan(enforce_approval=True)
            self.assertFalse(is_valid)
            self.assertTrue(any("HASH_MISMATCH" in err for err in errors))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_cli_approve_lock(self):
        with open(self.canonical_proposal_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name

        try:
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog_discovery.py")
            res = subprocess.run([sys.executable, script_path, "approve-lock", "--proposal", tmp_path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("LOCK_APPROVED=YES", res.stdout)
            self.assertIn("STATUS=READY_FOR_WAVE1_EXECUTION", res.stdout)

            # Now verify that wave1-preflight --enforce-approval succeeds
            verifier = Wave1PreflightVerifier(tmp_path)
            is_valid, plan, errors = verifier.verify_and_plan(enforce_approval=True)
            self.assertTrue(is_valid)
            self.assertTrue(plan["ready_for_execution"])
            self.assertTrue(plan["lock_approved"])
            self.assertEqual(plan["proposal_sha256"], "55087ef875573c7204251cd22ddd5fa92dd35b98321d95bcf41e60bddcc50d9f")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestWave2AvdConfigurator(unittest.TestCase):
    def test_wave2_canonical_constants(self):
        self.assertEqual(Wave2AvdConfigurator.CANONICAL_AVD_NAME, "alvorada_e1_api36_x86_64")
        self.assertEqual(Wave2AvdConfigurator.CANONICAL_PACKAGE, "system-images;android-36;default;x86_64")
        self.assertEqual(Wave2AvdConfigurator.CANONICAL_TAG, "default")
        self.assertEqual(Wave2AvdConfigurator.CANONICAL_ABI, "x86_64")

    def test_wave2_create_command_args(self):
        cmd = Wave2AvdConfigurator.get_create_command_args("pixel")
        self.assertIn("avdmanager", cmd)
        self.assertIn("alvorada_e1_api36_x86_64", cmd)
        self.assertIn("system-images;android-36;default;x86_64", cmd)
        self.assertIn("--force", cmd)

    def test_wave2_headless_launch_args(self):
        args = Wave2AvdConfigurator.get_headless_launch_args()
        self.assertIn("-no-window", args)
        self.assertIn("-no-boot-anim", args)
        self.assertIn("-no-snapshot", args)
        self.assertIn("-wipe-data", args)
        self.assertIn("-gpu", args)
        self.assertIn("swiftshader_indirect", args)
        self.assertIn("-accel", args)
        self.assertIn("on", args)

    def test_wave2_canonical_config_valid(self):
        cfg = Wave2AvdConfigurator.get_canonical_config()
        ok, errors = Wave2AvdConfigurator.verify_config(cfg)
        self.assertTrue(ok, f"Expected canonical config to be valid, got: {errors}")
        self.assertEqual(len(errors), 0)

    def test_wave2_verify_config_excessive_ram(self):
        cfg = Wave2AvdConfigurator.get_canonical_config()
        cfg["hw.ramSize"] = "4096"
        ok, errors = Wave2AvdConfigurator.verify_config(cfg)
        self.assertFalse(ok)
        self.assertTrue(any("RAM_EXCEEDS_HOST_BUDGET" in e for e in errors))

    def test_wave2_verify_config_excessive_cpu(self):
        cfg = Wave2AvdConfigurator.get_canonical_config()
        cfg["hw.cpu.ncore"] = "4"
        ok, errors = Wave2AvdConfigurator.verify_config(cfg)
        self.assertFalse(ok)
        self.assertTrue(any("CPU_CORES_EXCEED_HOST_BUDGET" in e for e in errors))

    def test_wave2_verify_config_wrong_abi(self):
        cfg = Wave2AvdConfigurator.get_canonical_config()
        cfg["abi.type"] = "arm64-v8a"
        ok, errors = Wave2AvdConfigurator.verify_config(cfg)
        self.assertFalse(ok)
        self.assertTrue(any("WRONG_ABI" in e for e in errors))

    def test_wave2_verify_config_wrong_tag(self):
        cfg = Wave2AvdConfigurator.get_canonical_config()
        cfg["tag.id"] = "google_apis"
        ok, errors = Wave2AvdConfigurator.verify_config(cfg)
        self.assertFalse(ok)
        self.assertTrue(any("WRONG_TAG" in e for e in errors))

    def test_cli_wave2_avd_spec(self):
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog_discovery.py")
        res = subprocess.run([sys.executable, script_path, "wave2-avd-spec", "--pretty"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["contract"], "ALVORADA_WAVE2_AVD_SPECIFICATION_V1")
        self.assertEqual(data["avd_name"], "alvorada_e1_api36_x86_64")
        self.assertEqual(data["target_package"], "system-images;android-36;default;x86_64")
        self.assertEqual(data["resource_budget"]["guest_ram_mb"], 2048)
        self.assertEqual(data["resource_budget"]["guest_vcpus"], 2)


if __name__ == "__main__":
    unittest.main()

