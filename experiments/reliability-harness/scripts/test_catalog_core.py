#!/usr/bin/env python3
"""
ALVORADA — Comprehensive Unit & Adversarial Test Suite for Catalog Core Contracts
Contract Version: RECOVERY-G1-001

Validates:
1. ALVORADA_CANONICAL_JSON_V1 test vectors (A through G) with STATIC SHA-256 FIXTURES.
2. Type safety and boundary negatives (NaN, Infinity, integer overflow/underflow, surrogates, timestamps, sets).
3. CatalogParser fail-closed states and independent revision tracking.
4. CatalogReadOnlyPolicy adversarial command rejection across whitespace, paths, quotes, and continuations.
"""

import hashlib
import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog_core import (
    CANONICAL_JSON_CONTRACT,
    MIN_SAFE_INTEGER,
    MAX_SAFE_INTEGER,
    validate_canonical_timestamp,
    validate_canonical_data,
    canonicalize_json_v1,
    hash_canonical_json_v1,
    json_loads_canonical,
    HARD_LOCK_PACKAGES,
    PACKAGE_STATE_ABSENT,
    PACKAGE_STATE_PRESENT_MATCHING,
    PACKAGE_STATE_PRESENT_DIFFERENT,
    PACKAGE_STATE_PARTIAL_OR_CORRUPT,
    PACKAGE_STATE_CATALOG_MISSING,
    PACKAGE_STATE_METADATA_AMBIGUOUS,
    ALL_PACKAGE_STATES,
    CatalogParser,
    CatalogReadOnlyPolicy,
)


class TestCanonicalJsonV1Vectors(unittest.TestCase):
    """
    Test vectors for ALVORADA_CANONICAL_JSON_V1 with STATIC PRE-COMPUTED FIXTURES.
    Expected digests are hardcoded fixtures, never dynamically computed and asserted.
    """

    # Static pre-computed SHA-256 fixture hashes
    FIXTURE_VECTOR_A = "d5984ccd500582b078a6fecb8ad8c320258df75c15ab02fe6f6127ccdd8915c6"
    FIXTURE_VECTOR_B = "d5984ccd500582b078a6fecb8ad8c320258df75c15ab02fe6f6127ccdd8915c6"
    FIXTURE_VECTOR_C = "ed0fd9d0e13933e2e448b16532674dc6f624391a8da25bf269a899785d4345c2"
    FIXTURE_VECTOR_D1 = "3d48f4efd0d2686a991cd8c44b7a5aab7b165d52e0d79dbe77353bdff9023b89"
    FIXTURE_VECTOR_D2 = "6fb35c4925e07e8f4463b71f6d487de48ad2824cc9a0c1c1e7e4dc44ac9c41e2"
    FIXTURE_VECTOR_E1 = "9285613f3642b142c4c9fa14b3f5edc943f949903d8313aa7a782312b691e112"
    FIXTURE_VECTOR_E2 = "cb005fd1af5f9ca93c3fd45ed4fb104ff32f5625911fafc10c8206dd3de16584"
    FIXTURE_VECTOR_F = "8df60e472cc1a89ed125d15211872fc554925315820efba26940084b4772b383"

    def test_vector_a_deterministic_key_sorting(self):
        """Vector A: Keys in different orders must produce identical bytes and static digest."""
        obj1 = {"z": 1, "a": 2, "m": {"k2": "v2", "k1": "v1"}}
        obj2 = {"a": 2, "m": {"k1": "v1", "k2": "v2"}, "z": 1}

        bytes1 = canonicalize_json_v1(obj1)
        bytes2 = canonicalize_json_v1(obj2)

        self.assertEqual(bytes1, bytes2)
        self.assertEqual(bytes1, b'{"a":2,"m":{"k1":"v1","k2":"v2"},"z":1}')
        self.assertEqual(hash_canonical_json_v1(obj1), self.FIXTURE_VECTOR_A)
        self.assertEqual(hash_canonical_json_v1(obj2), self.FIXTURE_VECTOR_A)

    def test_vector_b_whitespace_insignificance(self):
        """Vector B: Different whitespace in input JSON produces identical canonical bytes and static digest."""
        s1 = '{\n  "a": 2,\n  "m": {\n    "k1": "v1",\n    "k2": "v2"\n  },\n  "z": 1\n}'
        s2 = '{"z":1,"a":2,"m":{"k2":"v2","k1":"v1"}}'

        obj1 = json_loads_canonical(s1)
        obj2 = json_loads_canonical(s2)

        bytes1 = canonicalize_json_v1(obj1)
        bytes2 = canonicalize_json_v1(obj2)

        self.assertEqual(bytes1, bytes2)
        self.assertEqual(hash_canonical_json_v1(obj1), self.FIXTURE_VECTOR_B)
        self.assertEqual(hash_canonical_json_v1(obj2), self.FIXTURE_VECTOR_B)

    def test_vector_c_package_sorting_projection(self):
        """Vector C: Packages in different order before projection produce identical canonical output after normalization."""
        pkgs1 = [
            {"package_path": "emulator", "revision": "37.1.11"},
            {"package_path": "build-tools;36.0.0", "revision": "36.0.0"},
            {"package_path": "platform-tools", "revision": "36.0.0"},
        ]
        pkgs2 = [
            {"package_path": "platform-tools", "revision": "36.0.0"},
            {"package_path": "emulator", "revision": "37.1.11"},
            {"package_path": "build-tools;36.0.0", "revision": "36.0.0"},
        ]

        # Projection layer explicitly sorts by package_path
        norm1 = {"packages": sorted(pkgs1, key=lambda p: p["package_path"])}
        norm2 = {"packages": sorted(pkgs2, key=lambda p: p["package_path"])}

        bytes1 = canonicalize_json_v1(norm1)
        bytes2 = canonicalize_json_v1(norm2)

        self.assertEqual(bytes1, bytes2)
        self.assertEqual(hash_canonical_json_v1(norm1), self.FIXTURE_VECTOR_C)

    def test_vector_d_package_revision_differentiation(self):
        """Vector D: Different package revision produces different static digests."""
        pkg1 = {"package_path": "emulator", "revision": "37.1.11"}
        pkg2 = {"package_path": "emulator", "revision": "37.1.12"}

        h1 = hash_canonical_json_v1(pkg1)
        h2 = hash_canonical_json_v1(pkg2)

        self.assertNotEqual(h1, h2)
        self.assertEqual(h1, self.FIXTURE_VECTOR_D1)
        self.assertEqual(h2, self.FIXTURE_VECTOR_D2)

    def test_vector_e_gpu_mode_differentiation(self):
        """Vector E: Different GPU_MODE in lock payload produces different static digests."""
        payload1 = {"contract": "ALVORADA_LOCK_PAYLOAD_V1", "gpu_mode": "auto-no-window"}
        payload2 = {"contract": "ALVORADA_LOCK_PAYLOAD_V1", "gpu_mode": "swiftshader_indirect"}

        h1 = hash_canonical_json_v1(payload1)
        h2 = hash_canonical_json_v1(payload2)

        self.assertNotEqual(h1, h2)
        self.assertEqual(h1, self.FIXTURE_VECTOR_E1)
        self.assertEqual(h2, self.FIXTURE_VECTOR_E2)

    def test_vector_f_excluded_metadata(self):
        """Vector F: Excluded metadata yields identical digest across different metadata instances."""
        def project_excluding_metadata(data: dict) -> dict:
            return {k: v for k, v in data.items() if k != "metadata"}

        meta1 = {"contract": "TEST_CONTRACT", "id": "001", "metadata": {"ci_run": "111"}}
        meta2 = {"contract": "TEST_CONTRACT", "id": "001", "metadata": {"ci_run": "222"}}

        proj1 = project_excluding_metadata(meta1)
        proj2 = project_excluding_metadata(meta2)

        bytes1 = canonicalize_json_v1(proj1)
        bytes2 = canonicalize_json_v1(proj2)

        self.assertEqual(bytes1, bytes2)
        self.assertEqual(hash_canonical_json_v1(proj1), self.FIXTURE_VECTOR_F)

    def test_vector_g_float_rejection(self):
        """Vector G: Floats must fail closed with ValueError."""
        with self.assertRaises(ValueError):
            canonicalize_json_v1({"val": 1.23})

        with self.assertRaises(ValueError):
            canonicalize_json_v1({"val": 0.0})

        with self.assertRaises(ValueError):
            canonicalize_json_v1([1, 2, 3.14])

        with self.assertRaises(ValueError):
            json_loads_canonical('{"val": 1.23}')

        with self.assertRaises(ValueError):
            json_loads_canonical('{"val": 1e10}')


class TestCanonicalJsonTypeSafetyNegatives(unittest.TestCase):
    """Negative tests enforcing mathematical boundaries and type restrictions."""

    def test_nan_rejection(self):
        """NaN must fail closed."""
        with self.assertRaises(ValueError):
            canonicalize_json_v1({"val": float("nan")})

        with self.assertRaises(ValueError):
            json_loads_canonical('{"val": NaN}')

    def test_infinity_rejection(self):
        """Infinity and -Infinity must fail closed."""
        with self.assertRaises(ValueError):
            canonicalize_json_v1({"val": float("inf")})

        with self.assertRaises(ValueError):
            canonicalize_json_v1({"val": float("-inf")})

        with self.assertRaises(ValueError):
            json_loads_canonical('{"val": Infinity}')

        with self.assertRaises(ValueError):
            json_loads_canonical('{"val": -Infinity}')

    def test_integer_range_boundaries(self):
        """Integers strictly in [-9007199254740991, 9007199254740991]."""
        # Exact boundaries pass
        self.assertIsNotNone(canonicalize_json_v1({"min": MIN_SAFE_INTEGER}))
        self.assertIsNotNone(canonicalize_json_v1({"max": MAX_SAFE_INTEGER}))
        self.assertIsNotNone(canonicalize_json_v1({"zero": 0}))

        # Overflows fail closed
        with self.assertRaises(ValueError):
            canonicalize_json_v1({"overflow": MAX_SAFE_INTEGER + 1})

        with self.assertRaises(ValueError):
            canonicalize_json_v1({"underflow": MIN_SAFE_INTEGER - 1})

    def test_isolated_surrogate_rejection(self):
        """Isolated surrogates in strings or dictionary keys fail closed."""
        surrogate_char = chr(0xD800)
        with self.assertRaises(ValueError):
            canonicalize_json_v1({"value": f"bad_{surrogate_char}_string"})

        with self.assertRaises(ValueError):
            canonicalize_json_v1({f"bad_{surrogate_char}_key": 123})

        end_surrogate = chr(0xDFFF)
        with self.assertRaises(ValueError):
            canonicalize_json_v1({"value": f"bad_{end_surrogate}"})

    def test_set_rejection(self):
        """Sets are forbidden directly in canonical payload."""
        with self.assertRaises(TypeError):
            canonicalize_json_v1({"my_set": {1, 2, 3}})

        with self.assertRaises(TypeError):
            canonicalize_json_v1({1, 2, 3})

    def test_timestamp_validation(self):
        """Enforces YYYY-MM-DDTHH:MM:SSZ calendar contract."""
        # Valid
        validate_canonical_timestamp("2026-09-20T21:00:00Z")
        validate_canonical_timestamp("2024-02-29T12:00:00Z")  # Leap year

        # Milliseconds rejected
        with self.assertRaises(ValueError):
            validate_canonical_timestamp("2026-09-20T21:00:00.000Z")

        # Timezone offsets rejected
        with self.assertRaises(ValueError):
            validate_canonical_timestamp("2026-09-20T21:00:00+00:00")

        # Missing Z rejected
        with self.assertRaises(ValueError):
            validate_canonical_timestamp("2026-09-20T21:00:00")

        # Invalid calendar date (Feb 30th) rejected
        with self.assertRaises(ValueError):
            validate_canonical_timestamp("2026-02-30T12:00:00Z")

        # Non-string rejected
        with self.assertRaises(TypeError):
            validate_canonical_timestamp(123456789)


class TestCatalogParser(unittest.TestCase):
    """Validates CatalogParser fail-closed states and independent revision tracking."""

    SAMPLE_MATCHING_AND_ABSENT = """
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
  Description:        System Image
  Version:            2
"""

    SAMPLE_DIFFERENT_REVISION = """
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
  Description:        System Image
  Version:            2
"""

    SAMPLE_DUPLICATE_AMBIGUOUS = """
Available Packages:
--------------------------------------
emulator
  Description:        Android Emulator
  Version:            37.1.11

emulator
  Description:        Android Emulator Duplicate
  Version:            37.1.12
"""

    SAMPLE_CORRUPT_VERSION = """
Available Packages:
--------------------------------------
emulator
  Description:        Android Emulator with missing version
"""

    SAMPLE_CATALOG_MISSING = """
Installed packages:
--------------------------------------
emulator
  Description:        Android Emulator
  Version:            37.1.11

Available Packages:
--------------------------------------
platform-tools
  Description:        Android SDK Platform-Tools
  Version:            36.0.0
"""

    def test_parser_matching_and_absent_states(self):
        """Validates PRESENT_MATCHING_CATALOG and ABSENT states."""
        parser = CatalogParser(self.SAMPLE_MATCHING_AND_ABSENT)
        projection = parser.parse()

        self.assertEqual(projection["contract"], "ALVORADA_CATALOG_PROJECTION_V1")
        self.assertTrue(projection["is_complete"])
        self.assertFalse(projection["has_ambiguity"])

        pkgs = {p["package_path"]: p for p in projection["packages"]}

        # emulator was installed and matches available
        self.assertEqual(pkgs["emulator"]["state"], PACKAGE_STATE_PRESENT_MATCHING)
        self.assertEqual(pkgs["emulator"]["catalog_revision"], "37.1.11")
        self.assertEqual(pkgs["emulator"]["installed_revision"], "37.1.11")

        # platform-tools was available but not installed -> ABSENT
        self.assertEqual(pkgs["platform-tools"]["state"], PACKAGE_STATE_ABSENT)
        self.assertEqual(pkgs["platform-tools"]["catalog_revision"], "36.0.0")
        self.assertIsNone(pkgs["platform-tools"]["installed_revision"])

    def test_parser_different_revision_state(self):
        """Validates PRESENT_DIFFERENT_REVISION with independent revisions."""
        parser = CatalogParser(self.SAMPLE_DIFFERENT_REVISION)
        projection = parser.parse()

        pkgs = {p["package_path"]: p for p in projection["packages"]}
        emu = pkgs["emulator"]

        self.assertEqual(emu["state"], PACKAGE_STATE_PRESENT_DIFFERENT)
        self.assertEqual(emu["installed_revision"], "35.0.0")
        self.assertEqual(emu["catalog_revision"], "37.1.11")

    def test_parser_duplicate_ambiguous_fails_closed(self):
        """Validates duplicate package triggers METADATA_AMBIGUOUS and fails closed."""
        parser = CatalogParser(self.SAMPLE_DUPLICATE_AMBIGUOUS)
        projection = parser.parse()

        self.assertTrue(projection["has_ambiguity"])
        self.assertFalse(projection["is_complete"])

        pkgs = {p["package_path"]: p for p in projection["packages"]}
        self.assertEqual(pkgs["emulator"]["state"], PACKAGE_STATE_METADATA_AMBIGUOUS)

    def test_parser_corrupt_entry_fails_closed(self):
        """Validates missing version field triggers PARTIAL_OR_CORRUPT."""
        parser = CatalogParser(self.SAMPLE_CORRUPT_VERSION)
        projection = parser.parse()

        self.assertFalse(projection["is_complete"])
        pkgs = {p["package_path"]: p for p in projection["packages"]}
        self.assertEqual(pkgs["emulator"]["state"], PACKAGE_STATE_PARTIAL_OR_CORRUPT)

    def test_parser_catalog_entry_missing_state(self):
        """Validates CATALOG_ENTRY_MISSING when installed package lacks catalog entry."""
        parser = CatalogParser(self.SAMPLE_CATALOG_MISSING)
        projection = parser.parse()

        pkgs = {p["package_path"]: p for p in projection["packages"]}
        self.assertEqual(pkgs["emulator"]["state"], PACKAGE_STATE_CATALOG_MISSING)

    def test_parser_output_has_no_approval_or_lock(self):
        """Validates projection does NOT contain lock approval, lock digest, or proposal bypass."""
        parser = CatalogParser(self.SAMPLE_MATCHING_AND_ABSENT)
        projection = parser.parse()

        self.assertNotIn("lock_approved", projection)
        self.assertNotIn("lock_digest", projection)
        self.assertNotIn("proposal_sha256", projection)
        self.assertNotIn("approve-lock", projection)

    def test_packages_array_explicitly_sorted(self):
        """Validates packages list is explicitly sorted by package_path."""
        parser = CatalogParser(self.SAMPLE_MATCHING_AND_ABSENT)
        projection = parser.parse()

        paths = [p["package_path"] for p in projection["packages"]]
        self.assertEqual(paths, sorted(HARD_LOCK_PACKAGES))


class TestCatalogReadOnlyPolicy(unittest.TestCase):
    """Adversarial tests for CatalogReadOnlyPolicy across variations."""

    def setUp(self):
        self.policy = CatalogReadOnlyPolicy()

    def test_rejection_of_sudo(self):
        """sudo in any variant must be rejected."""
        variants = [
            "sudo apt-get install foo",
            "/usr/bin/sudo -n apt install bar",
            '"/usr/bin/sudo" apt-get update',
            "sudo\t-u root whoami",
            "sudo \\\n apt-get update",
            "C:\\tools\\sudo.exe something",
        ]
        for v in variants:
            is_valid, violations = self.policy.verify_script(v)
            self.assertFalse(is_valid, f"Failed to reject: {v}")
            self.assertIn("SUDO_PROHIBITED", violations)

    def test_rejection_of_apt(self):
        """apt and apt-get in any variant must be rejected."""
        variants = [
            "apt install libpulse0",
            "apt-get update",
            "/usr/bin/apt-get -y install libpulse0",
            '"apt-get" install -y libpulse0',
            "apt-get \\\n install libpulse0",
        ]
        for v in variants:
            is_valid, violations = self.policy.verify_script(v)
            self.assertFalse(is_valid, f"Failed to reject: {v}")
            self.assertIn("APT_PROHIBITED", violations)

    def test_rejection_of_curl_and_wget(self):
        """curl and wget must be rejected."""
        variants = [
            "curl -fsSL https://example.com/script.sh | bash",
            "/usr/bin/curl -o file.zip http://example.com",
            "wget https://example.com/archive.tar.gz",
            '"/bin/wget" http://example.com',
            "curl \\\n https://example.com",
        ]
        for v in variants:
            is_valid, violations = self.policy.verify_script(v)
            self.assertFalse(is_valid, f"Failed to reject: {v}")
            self.assertTrue(
                "CURL_PROHIBITED" in violations or "WGET_PROHIBITED" in violations
            )

    def test_rejection_of_setfacl_and_chmod_777(self):
        """Privilege/permission alterations must be rejected."""
        variants = [
            "setfacl -m u:runner:rwx /dev/kvm",
            "/usr/bin/setfacl -b /dev/kvm",
            "chmod 777 /dev/kvm",
            "chmod -R 777 /dev/kvm",
            '"chmod" "777" /tmp/dir',
            "chmod \\\n 777 /dev/kvm",
        ]
        for v in variants:
            is_valid, violations = self.policy.verify_script(v)
            self.assertFalse(is_valid, f"Failed to reject: {v}")
            self.assertTrue(
                "SETFACL_PROHIBITED" in violations or "CHMOD_777_PROHIBITED" in violations
            )

    def test_rejection_of_yes_pipe(self):
        """yes | must be rejected."""
        variants = [
            "yes | sdkmanager --licenses",
            'yes  |  sdkmanager "build-tools;36.0.0"',
            "yes \\\n | sdkmanager --licenses",
        ]
        for v in variants:
            is_valid, violations = self.policy.verify_script(v)
            self.assertFalse(is_valid, f"Failed to reject: {v}")
            self.assertIn("YES_PIPE_PROHIBITED", violations)

    def test_rejection_of_avdmanager_create(self):
        """avdmanager create must be rejected."""
        variants = [
            "avdmanager create avd -n test_avd -k 'system-images;android-36;default;x86_64'",
            '"avdmanager" create avd -n test',
            "/opt/cmdline-tools/bin/avdmanager.bat create avd",
            "avdmanager \\\n create avd",
        ]
        for v in variants:
            is_valid, violations = self.policy.verify_script(v)
            self.assertFalse(is_valid, f"Failed to reject: {v}")
            self.assertIn("AVD_CREATE_PROHIBITED", violations)

    def test_rejection_of_adb_install(self):
        """adb install must be rejected."""
        variants = [
            "adb install app.apk",
            'adb.exe -s emulator-5554 install "app-debug.apk"',
            '"/usr/bin/adb" install -r test.apk',
            "adb \\\n install test.apk",
        ]
        for v in variants:
            is_valid, violations = self.policy.verify_script(v)
            self.assertFalse(is_valid, f"Failed to reject: {v}")
            self.assertIn("ADB_INSTALL_PROHIBITED", violations)

    def test_rejection_of_sdkmanager_mutations(self):
        """sdkmanager mutation flags must be rejected."""
        variants = [
            'sdkmanager --install "build-tools;36.0.0"',
            'sdkmanager "--install" "build-tools;36.0.0"',
            "sdkmanager --update",
            "sdkmanager --uninstall emulator",
            "sdkmanager --licenses",
        ]
        for v in variants:
            is_valid, violations = self.policy.verify_script(v)
            self.assertFalse(is_valid, f"Failed to reject: {v}")
            self.assertIn("SDK_MUTATION_PROHIBITED", violations)

    def test_rejection_of_emulator_avd_launches(self):
        """emulator -avd or @ launches must be rejected in script."""
        variants = [
            "emulator -avd test_avd",
            "emulator @test_avd",
            '"emulator.exe" -avd my_device',
            "emulator \\\n -avd test",
        ]
        for v in variants:
            is_valid, violations = self.policy.verify_script(v)
            self.assertFalse(is_valid, f"Failed to reject: {v}")
            self.assertIn("EMULATOR_AVD_PROHIBITED", violations)

    def test_emulator_invocation_allowlist(self):
        """
        emulator invocation directly checked:
        Only allowed:
        - ['-help']
        - ['-help-gpu'] (ONLY when help_proved_gpu is True)
        """
        # Allowed
        valid, err = self.policy.verify_emulator_invocation(["-help"])
        self.assertTrue(valid)
        self.assertIsNone(err)

        valid, err = self.policy.verify_emulator_invocation(["-help-gpu"], help_proved_gpu=True)
        self.assertTrue(valid)
        self.assertIsNone(err)

        # Rejected: -help-gpu without prior proof
        valid, err = self.policy.verify_emulator_invocation(["-help-gpu"], help_proved_gpu=False)
        self.assertFalse(valid)
        self.assertEqual(err, "GPU_HELP_INTERFACE_NOT_PREVIOUSLY_PROVED")

        # Rejected: all other arguments
        disallowed_args = [
            [],
            ["-version"],
            ["-avd", "test"],
            ["@test"],
            ["-no-window"],
            ["-accel-check"],
        ]
        for args in disallowed_args:
            valid, err = self.policy.verify_emulator_invocation(args)
            self.assertFalse(valid, f"Expected rejection for args: {args}")
            self.assertTrue("UNAUTHORIZED_EMULATOR_ARGUMENTS" in err)

    def test_allowed_read_only_scripts(self):
        """Pure read-only discovery commands pass the policy."""
        allowed_scripts = [
            "sdkmanager --list --verbose --channel=0",
            "emulator -help",
            'echo "Validating environment"',
        ]
        for s in allowed_scripts:
            is_valid, violations = self.policy.verify_script(s)
            self.assertTrue(is_valid, f"Expected pass, got violations {violations} for: {s}")


if __name__ == "__main__":
    unittest.main()
