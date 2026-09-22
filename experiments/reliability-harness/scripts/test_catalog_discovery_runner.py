#!/usr/bin/env python3
"""
ALVORADA — Unit Tests for Catalog Discovery Runner
Campaign: ALVORADA G1 EMPIRICAL ACCELERATION CAMPAIGN 001 (Phase 1)
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

from catalog_core import (
    canonicalize_json_v1,
    hash_canonical_json_v1,
    CatalogReadOnlyPolicy,
    HARD_LOCK_PACKAGES,
)
from catalog_discovery_runner import (
    resolve_sdk_root,
    resolve_sdkmanager,
    get_cmdline_tools_revision,
    build_and_verify_sdkmanager_command,
    generate_catalog_evidence_text,
    run_catalog_discovery,
)


SAMPLE_COMPLETE_RAW_CATALOG = """
Installed packages:
--------------------------------------
build-tools;36.0.0
  Description:        Android SDK Build-Tools 36.0.0
  Version:            36.0.0
  Installed Location: /sdk/build-tools/36.0.0

platform-tools
  Description:        Android SDK Platform-Tools
  Version:            37.0.1
  Installed Location: /sdk/platform-tools

platforms;android-36
  Description:        Android SDK Platform 36
  Version:            2
  Installed Location: /sdk/platforms/android-36

Available Packages:
--------------------------------------
build-tools;36.0.0
  Description:        Android SDK Build-Tools 36.0.0
  Version:            36.0.0

emulator
  Description:        Android Emulator
  Version:            37.1.11

platform-tools
  Description:        Android SDK Platform-Tools
  Version:            37.0.1

platforms;android-36
  Description:        Android SDK Platform 36
  Version:            2

system-images;android-36;default;x86_64
  Description:        System Image
  Version:            2
"""

SAMPLE_INCOMPLETE_RAW_CATALOG = """
Available Packages:
--------------------------------------
build-tools;36.0.0
  Description:        Android SDK Build-Tools 36.0.0
  Version:            36.0.0

emulator
  Description:        Android Emulator
  Version:            37.1.11
"""


class TestCatalogDiscoveryRunner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="alvorada_test_runner_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sdk_root_resolution_override(self):
        sdk_dir = os.path.join(self.temp_dir, "fake_sdk")
        os.makedirs(sdk_dir, exist_ok=True)
        resolved = resolve_sdk_root(override_path=sdk_dir)
        self.assertEqual(resolved, os.path.abspath(sdk_dir))

    def test_sdk_root_resolution_not_found(self):
        with self.assertRaises(FileNotFoundError):
            resolve_sdk_root(override_path=os.path.join(self.temp_dir, "nonexistent"))

    def test_sdkmanager_resolution_override(self):
        fake_bin = os.path.join(self.temp_dir, "fake_sdkmanager")
        with open(fake_bin, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(fake_bin, 0o755)

        resolved = resolve_sdkmanager(self.temp_dir, override_path=fake_bin)
        self.assertEqual(resolved, os.path.abspath(fake_bin))

    def test_sdkmanager_resolution_in_cmdline_tools(self):
        cmdline_bin = os.path.join(self.temp_dir, "cmdline-tools", "latest", "bin")
        os.makedirs(cmdline_bin, exist_ok=True)
        fake_bin = os.path.join(cmdline_bin, "sdkmanager")
        with open(fake_bin, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(fake_bin, 0o755)

        resolved = resolve_sdkmanager(self.temp_dir)
        self.assertEqual(resolved, os.path.abspath(fake_bin))

    def test_cmdline_tools_revision_reading(self):
        cmdline_dir = os.path.join(self.temp_dir, "cmdline-tools", "latest")
        bin_dir = os.path.join(cmdline_dir, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        fake_bin = os.path.join(bin_dir, "sdkmanager")
        with open(fake_bin, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(fake_bin, 0o755)

        props_file = os.path.join(cmdline_dir, "source.properties")
        with open(props_file, "w") as f:
            f.write("Pkg.Revision=19.0\nPkg.Path=cmdline-tools;latest\n")

        rev = get_cmdline_tools_revision(self.temp_dir, fake_bin)
        self.assertEqual(rev, "19.0")

    def test_build_and_verify_sdkmanager_command(self):
        sdk_root = "/mock/sdk/root"
        fake_bin = "/mock/sdk/root/cmdline-tools/latest/bin/sdkmanager"

        full_argv, args = build_and_verify_sdkmanager_command(sdk_root, fake_bin)

        self.assertEqual(full_argv[0], fake_bin)
        self.assertEqual(args, [
            f"--sdk_root={sdk_root}",
            "--list",
            "--verbose",
            "--channel=0",
        ])

        # Verify against CatalogReadOnlyPolicy
        policy = CatalogReadOnlyPolicy()
        valid, err = policy.verify_sdkmanager_invocation(args)
        self.assertTrue(valid)
        self.assertIsNone(err)

    def test_run_catalog_discovery_mock_complete(self):
        raw_file = os.path.join(self.temp_dir, "raw_catalog.txt")
        with open(raw_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_COMPLETE_RAW_CATALOG)

        out_dir = os.path.join(self.temp_dir, "artifacts")
        exit_code, projection, digests = run_catalog_discovery(
            output_dir=out_dir,
            sdk_root_override="/mock/sdk",
            sdkmanager_override="/mock/sdk/bin/sdkmanager",
            repo_sha="12245b5a1db9cb04495b7d04d8960ae67841d4a3",
            run_id="999888",
            observed_at="2026-09-21T12:00:00Z",
            raw_input_file=raw_file,
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(projection["is_complete"])
        self.assertFalse(projection["has_ambiguity"])
        self.assertEqual(len(projection["packages"]), 5)

        # Check artifact files exist
        proj_file = os.path.join(out_dir, "catalog-projection.json")
        evid_file = os.path.join(out_dir, "catalog-evidence.txt")
        chk_file = os.path.join(out_dir, "checksums.sha256")

        self.assertTrue(os.path.isfile(proj_file))
        self.assertTrue(os.path.isfile(evid_file))
        self.assertTrue(os.path.isfile(chk_file))

        # Check raw output was not saved in out_dir
        self.assertFalse(os.path.isfile(os.path.join(out_dir, "raw_catalog.txt")))
        self.assertFalse(os.path.isfile(os.path.join(out_dir, "raw_sdk_catalog.txt")))

        # Verify checksums match files
        with open(proj_file, "rb") as f:
            proj_data = f.read()
            # Must end with \n for posix standard
            self.assertTrue(proj_data.endswith(b"\n"))
            canon_bytes = proj_data[:-1]
            actual_proj_sha = hashlib.sha256(canon_bytes).hexdigest()
            self.assertEqual(actual_proj_sha, digests["projection_sha256"])

        with open(evid_file, "rb") as f:
            actual_evid_sha = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(actual_evid_sha, digests["evidence_sha256"])

        with open(chk_file, "r", encoding="utf-8") as f:
            chk_lines = f.read().splitlines()
            self.assertEqual(len(chk_lines), 2)
            self.assertEqual(
                chk_lines[0], f"{digests['projection_sha256']}  catalog-projection.json"
            )
            self.assertEqual(
                chk_lines[1], f"{digests['evidence_sha256']}  catalog-evidence.txt"
            )

        # Check evidence text contains key sections
        with open(evid_file, "r", encoding="utf-8") as f:
            evid_text = f.read()
            self.assertIn("ALVORADA CATALOG DISCOVERY EVIDENCE REPORT", evid_text)
            self.assertIn("Repository Commit SHA: 12245b5a1db9cb04495b7d04d8960ae67841d4a3", evid_text)
            self.assertIn("Catalog Run ID: 999888", evid_text)
            self.assertIn("Catalog Digest: " + digests["catalog_digest"], evid_text)
            self.assertIn("Package: emulator", evid_text)
            self.assertIn("State: ABSENT", evid_text)

    def test_run_catalog_discovery_mock_incomplete(self):
        raw_file = os.path.join(self.temp_dir, "raw_incomplete.txt")
        with open(raw_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_INCOMPLETE_RAW_CATALOG)

        out_dir = os.path.join(self.temp_dir, "artifacts")
        exit_code, projection, digests = run_catalog_discovery(
            output_dir=out_dir,
            raw_input_file=raw_file,
        )

        self.assertEqual(exit_code, 2)
        self.assertFalse(projection["is_complete"])
        self.assertEqual(digests["catalog_digest"], "INCOMPLETE_OR_AMBIGUOUS_CATALOG")

    def test_invalid_observation_timestamp_fails_closed(self):
        raw_file = os.path.join(self.temp_dir, "raw_catalog.txt")
        with open(raw_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_COMPLETE_RAW_CATALOG)

        out_dir = os.path.join(self.temp_dir, "artifacts")
        with self.assertRaises(ValueError):
            run_catalog_discovery(
                output_dir=out_dir,
                observed_at="2026-09-21 12:00:00",  # Invalid format (no T or Z)
                raw_input_file=raw_file,
            )


if __name__ == "__main__":
    unittest.main()
