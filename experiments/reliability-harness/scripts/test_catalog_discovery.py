#!/usr/bin/env python3
"""
Unit tests for ALVORADA Catalog Discovery Engine and Static Policy Verifier
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog_discovery import (
    canonicalize_json_v1,
    hash_canonical_json_v1,
    CatalogParser,
    StaticPolicyVerifier,
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


if __name__ == "__main__":
    unittest.main()
