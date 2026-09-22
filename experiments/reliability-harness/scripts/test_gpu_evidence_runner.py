#!/usr/bin/env python3
"""
ALVORADA — Unit Test Suite for Ephemeral GPU Capability Evidence Runner
Campaign: ALVORADA G1 EMPIRICAL ACCELERATION CAMPAIGN 001 (Phase 2)
"""

import copy
import hashlib
import json
import os
import shutil
import tempfile
import unittest

from catalog_core import canonicalize_json_v1
from catalog_lock_model import (
    ALLOWED_GPU_EVIDENCE_KEYS,
    create_lock_proposal,
    create_catalog_digest_payload,
)
from gpu_evidence_runner import (
    build_gpu_evidence,
    check_libpulse,
    extract_package_xml_revision,
    extract_source_properties_revision,
    is_strict_header,
    parse_gpu_help_output,
    run_gpu_evidence_probe,
    verify_installed_emulator_revision,
)


class TestGpuHelpHeaderDetector(unittest.TestCase):
    """Tests the strict and flexible header detection regex."""

    def test_valid_headers(self):
        valid_headers = [
            "Valid gpu modes are:",
            "valid gpu modes are:",
            "VALID GPU MODES ARE:",
            "Supported gpu modes:",
            "supported gpu modes are:",
            "Available gpu modes:",
            "available gpu modes are:",
            "GPU modes:",
            "gpu modes are:",
            "gpu modes available:",
            "gpu modes supported:",
            "Select one of the following gpu modes:",
            "One of the following gpu modes:",
            "The following gpu modes are supported:",
        ]
        for h in valid_headers:
            self.assertTrue(is_strict_header(h), f"Expected True for header: {h!r}")

    def test_invalid_headers(self):
        invalid_headers = [
            "",
            "   ",
            "Valid gpu modes are",  # missing colon
            "Supported display modes:",  # no gpu
            "GPU options:",  # no mode/modes
            "Random text with gpu and modes",  # no colon
            "Usage: emulator [options] -gpu <mode>",  # not a header
            "Valid gpu modes are: extra text",  # colon not at end
        ]
        for h in invalid_headers:
            self.assertFalse(is_strict_header(h), f"Expected False for invalid header: {h!r}")


class TestGpuHelpParser(unittest.TestCase):
    """Tests parser variations and fail-closed protections."""

    def test_standard_valid_gpu_modes_are_described(self):
        raw = """\
Android Emulator GPU Help:
Valid gpu modes are:
    auto: Use host GPU if available, otherwise fallback to swiftshader.
    host: Desktop OpenGL graphics.
    swiftshader_indirect: Quick execution using SwiftShader CPU rasterizer.
    angle_indirect: Direct3D 11 / Metal translation via ANGLE.
    guest: Guest-side software rendering.
    off: No GPU emulation.
"""
        status, candidates = parse_gpu_help_output(raw)
        self.assertEqual(status, "PASS_STRICT")
        expected = [
            "angle_indirect",
            "auto",
            "guest",
            "host",
            "off",
            "swiftshader_indirect",
        ]
        self.assertEqual(candidates, expected)

    def test_supported_gpu_modes_bare_tokens(self):
        raw = """\
Supported gpu modes:
  auto
  host
  swiftshader_indirect
  off
"""
        status, candidates = parse_gpu_help_output(raw)
        self.assertEqual(status, "PASS_STRICT")
        self.assertEqual(candidates, ["auto", "host", "off", "swiftshader_indirect"])

    def test_multi_line_descriptions_and_continuation_lines(self):
        raw = """\
Available gpu modes are:
  auto: Automatically detect host capabilities and select
        the best graphics renderer.
  host: Direct hardware acceleration through desktop OpenGL
        or Vulkan driver.
  off: Complete software fallback without GPU hardware.

Note: on headless servers, use swiftshader_indirect or off.
"""
        status, candidates = parse_gpu_help_output(raw)
        self.assertEqual(status, "PASS_STRICT")
        self.assertEqual(candidates, ["auto", "host", "off"])

    def test_dash_bullet_candidates(self):
        raw = """\
The following gpu modes are supported:
  - auto: Automatic detection
  - host: Desktop host
  - off: Disabled
"""
        status, candidates = parse_gpu_help_output(raw)
        self.assertEqual(status, "PASS_STRICT")
        self.assertEqual(candidates, ["auto", "host", "off"])

    def test_quoted_tokens_and_diagnostic_warnings(self):
        raw = """\
INFO    | Android Emulator version 37.1.11
WARNING | No display found
Valid values for -gpu are:
WARNING | Failed to probe hardware acceleration
  'auto': host detection
  'host': desktop GL
  'swiftshader_indirect': CPU renderer
  'off': disabled
"""
        status, candidates = parse_gpu_help_output(raw)
        self.assertEqual(status, "PASS_STRICT")
        self.assertEqual(candidates, ["auto", "host", "off", "swiftshader_indirect"])

    def test_inline_comma_separated_modes(self):
        raw = """\
Valid gpu modes are: auto, host, swiftshader_indirect, off
"""
        status, candidates = parse_gpu_help_output(raw)
        self.assertEqual(status, "PASS_STRICT")
        self.assertEqual(candidates, ["auto", "host", "off", "swiftshader_indirect"])

    def test_unrecognized_header_fails_ambiguous(self):
        raw = """\
Options for GPU rendering:
  auto - automatic
  host - desktop
  swiftshader_indirect - software
  off - none
"""
        status, candidates = parse_gpu_help_output(raw)
        self.assertEqual(status, "AMBIGUOUS")
        self.assertEqual(candidates, [])

    def test_empty_output_fails_unavailable(self):
        status, candidates = parse_gpu_help_output("")
        self.assertEqual(status, "UNAVAILABLE")
        self.assertEqual(candidates, [])

        status, candidates = parse_gpu_help_output("   \n\n  ")
        self.assertEqual(status, "UNAVAILABLE")
        self.assertEqual(candidates, [])

    def test_missing_header_fails_ambiguous(self):
        raw = """\
emulator: unknown option -help-gpu
Run emulator -help for options.
"""
        status, candidates = parse_gpu_help_output(raw)
        self.assertEqual(status, "AMBIGUOUS")
        self.assertEqual(candidates, [])

    def test_duplicate_headers_fail_ambiguous(self):
        raw = """\
Valid gpu modes are:
  auto: host
Supported gpu modes:
  off: disabled
"""
        status, candidates = parse_gpu_help_output(raw)
        self.assertEqual(status, "AMBIGUOUS")
        self.assertEqual(candidates, [])

    def test_excluded_keyword_fails_ambiguous(self):
        raw = """\
Valid gpu modes are:
  note: please remember to install drivers
  auto: automatic host
"""
        status, candidates = parse_gpu_help_output(raw)
        self.assertEqual(status, "AMBIGUOUS")
        self.assertEqual(candidates, [])

    def test_inconsistent_indent_fails_ambiguous(self):
        raw = """\
Valid gpu modes are:
  auto: host
    host: desktop
"""
        status, candidates = parse_gpu_help_output(raw)
        self.assertEqual(status, "AMBIGUOUS")
        self.assertEqual(candidates, [])


class TestMetadataParsers(unittest.TestCase):
    """Tests package.xml and source.properties revision extraction."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_package_xml_parser_valid(self):
        xml_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ns2:repository xmlns:ns2="http://schemas.android.com/repository/android/common/02">
    <localPackage path="emulator" obsolete="false">
        <type-details xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="ns2:genericDetailsType"/>
        <revision>
            <major>37</major>
            <minor>1</minor>
            <micro>11</micro>
        </revision>
        <display-name>Android Emulator</display-name>
    </localPackage>
</ns2:repository>
"""
        xml_path = os.path.join(self.temp_dir, "package.xml")
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        rev = extract_package_xml_revision(xml_path)
        self.assertEqual(rev, "37.1.11")

    def test_package_xml_parser_corrupt(self):
        xml_path = os.path.join(self.temp_dir, "corrupt.xml")
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write("NOT_XML")
        self.assertIsNone(extract_package_xml_revision(xml_path))

    def test_source_properties_parser_valid(self):
        props_content = """\
Pkg.Desc=Android Emulator
Pkg.Revision=37.1.11
"""
        props_path = os.path.join(self.temp_dir, "source.properties")
        with open(props_path, "w", encoding="utf-8") as f:
            f.write(props_content)

        rev = extract_source_properties_revision(props_path)
        self.assertEqual(rev, "37.1.11")

    def test_source_properties_parser_corrupt(self):
        props_path = os.path.join(self.temp_dir, "bad.properties")
        with open(props_path, "w", encoding="utf-8") as f:
            f.write("NO_REVISION_KEY=YES\n")
        self.assertIsNone(extract_source_properties_revision(props_path))

    def test_verify_installed_emulator_revision_match(self):
        emu_dir = os.path.join(self.temp_dir, "emulator")
        os.makedirs(emu_dir)
        with open(os.path.join(emu_dir, "package.xml"), "w", encoding="utf-8") as f:
            f.write("""<repo><revision><major>37</major><minor>1</minor><micro>11</micro></revision></repo>""")
        with open(os.path.join(emu_dir, "source.properties"), "w", encoding="utf-8") as f:
            f.write("Pkg.Revision=37.1.11\n")

        valid, rev = verify_installed_emulator_revision(self.temp_dir, "37.1.11")
        self.assertTrue(valid)
        self.assertEqual(rev, "37.1.11")

    def test_verify_installed_emulator_revision_conflict(self):
        emu_dir = os.path.join(self.temp_dir, "emulator")
        os.makedirs(emu_dir)
        with open(os.path.join(emu_dir, "package.xml"), "w", encoding="utf-8") as f:
            f.write("""<repo><revision><major>37</major><minor>1</minor><micro>11</micro></revision></repo>""")
        with open(os.path.join(emu_dir, "source.properties"), "w", encoding="utf-8") as f:
            f.write("Pkg.Revision=37.1.10\n")

        valid, err = verify_installed_emulator_revision(self.temp_dir, "37.1.11")
        self.assertFalse(valid)
        self.assertIn("EMULATOR_METADATA_CONFLICT", err)

    def test_verify_installed_emulator_revision_mismatch_with_candidate(self):
        emu_dir = os.path.join(self.temp_dir, "emulator")
        os.makedirs(emu_dir)
        with open(os.path.join(emu_dir, "package.xml"), "w", encoding="utf-8") as f:
            f.write("""<repo><revision><major>35</major><minor>0</minor><micro>0</micro></revision></repo>""")
        with open(os.path.join(emu_dir, "source.properties"), "w", encoding="utf-8") as f:
            f.write("Pkg.Revision=35.0.0\n")

        valid, err = verify_installed_emulator_revision(self.temp_dir, "37.1.11")
        self.assertFalse(valid)
        self.assertIn("EMULATOR_REVISION_MISMATCH", err)


class TestGpuEvidenceBuilderAndContract(unittest.TestCase):
    """Verifies that gpu_evidence integrates seamlessly with catalog_lock_model."""

    def test_build_gpu_evidence_ready_pass_strict(self):
        ev = build_gpu_evidence(
            candidate_modes=["swiftshader_indirect", "auto", "off"],
            emulator_revision="37.1.11",
            parser_status="PASS_STRICT",
            projection_sha256="64f3ddd82cc72dacc9146e492345d1f7db8196cff053d7343521021140a7404e",
            status="PASS_STRICT",
        )
        self.assertEqual(set(ev.keys()), ALLOWED_GPU_EVIDENCE_KEYS)
        self.assertTrue(ev["evidence_ready"])
        self.assertEqual(ev["candidate_modes"], ["auto", "off", "swiftshader_indirect"])
        self.assertEqual(ev["emulator_revision"], "37.1.11")
        self.assertEqual(ev["parser_status"], "PASS_STRICT")
        self.assertEqual(ev["status"], "PASS_STRICT")

    def test_build_gpu_evidence_not_ready_on_failure(self):
        ev = build_gpu_evidence(
            candidate_modes=[],
            emulator_revision="37.1.11",
            parser_status="FAILED",
            projection_sha256="64f3ddd82cc72dacc9146e492345d1f7db8196cff053d7343521021140a7404e",
            status="FAILED",
        )
        self.assertFalse(ev["evidence_ready"])

    def test_gpu_evidence_integrates_with_lock_proposal(self):
        """Verifies that constructed gpu_evidence successfully produces a valid proposal."""
        projection = {
            "contract": "ALVORADA_CATALOG_PROJECTION_V1",
            "has_ambiguity": False,
            "is_complete": True,
            "packages": [
                {"catalog_revision": "36.0.0", "installed_revision": "36.0.0", "package_path": "build-tools;36.0.0", "state": "PRESENT_MATCHING_CATALOG"},
                {"catalog_revision": "37.1.11", "installed_revision": None, "package_path": "emulator", "state": "ABSENT"},
                {"catalog_revision": "37.0.1", "installed_revision": "37.0.1", "package_path": "platform-tools", "state": "PRESENT_MATCHING_CATALOG"},
                {"catalog_revision": "2", "installed_revision": "2", "package_path": "platforms;android-36", "state": "PRESENT_MATCHING_CATALOG"},
                {"catalog_revision": "2", "installed_revision": None, "package_path": "system-images;android-36;default;x86_64", "state": "ABSENT"},
            ],
        }
        cat_payload = create_catalog_digest_payload(projection)
        env = {
            "cmdline_tools_revision": "12.0",
            "emulator_revision": "37.1.11",
            "jdk_major": 17,
            "runner_image_label": "ubuntu24",
            "runner_image_version": "20260907.300.1",
            "runner_os": "Linux",
        }
        prov = {
            "catalog_run_id": "35676154497",
            "repository_commit_sha": "8570a837852a2ab669092ac3940086a1fdc1cb81",
            "runner_image_label": "ubuntu24",
            "runner_image_version": "20260907.300.1",
        }
        fresh = {
            "fresh_until": "2026-09-29T01:32:53Z",
            "max_age_days": 7,
            "observed_at": "2026-09-22T01:32:53Z",
        }
        gpu = build_gpu_evidence(
            candidate_modes=["auto", "off", "swiftshader_indirect"],
            emulator_revision="37.1.11",
            parser_status="PASS_STRICT",
            projection_sha256="64f3ddd82cc72dacc9146e492345d1f7db8196cff053d7343521021140a7404e",
            status="PASS_STRICT",
        )

        proposal = create_lock_proposal(
            catalog_digest_payload=cat_payload,
            environment=env,
            gpu_evidence=gpu,
            freshness=fresh,
            provenance=prov,
        )
        self.assertTrue(proposal["ready_for_human_review"])
        self.assertEqual(proposal["proposal_state"], "PENDING_HUMAN_REVIEW")
        self.assertEqual(proposal["gpu_evidence"]["candidate_modes"], ["auto", "off", "swiftshader_indirect"])


class TestOrchestrationOffline(unittest.TestCase):
    """Tests full runner orchestration in offline replay mode."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.out_dir = os.path.join(self.temp_dir, "artifacts")
        self.raw_help_file = os.path.join(self.temp_dir, "raw_help.txt")
        self.raw_help_gpu_file = os.path.join(self.temp_dir, "raw_help_gpu.txt")

        with open(self.raw_help_file, "w", encoding="utf-8") as f:
            f.write("""\
Android Emulator usage:
  emulator [options] [-qemu args]
Valid options for -help are:
  -help-all
  -help-gpu
  -help-disk-images
""")

        with open(self.raw_help_gpu_file, "w", encoding="utf-8") as f:
            f.write("""\
Valid gpu modes are:
    auto: Use host GPU if available, otherwise fallback to swiftshader.
    host: Desktop OpenGL graphics.
    swiftshader_indirect: SwiftShader CPU rasterizer.
    angle_indirect: ANGLE D3D11 / Metal.
    guest: Guest-side software rendering.
    off: No GPU emulation.
""")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_offline_orchestration_artifacts_and_checksums(self):
        exit_code, gpu_ev, ev_sha = run_gpu_evidence_probe(
            output_dir=self.out_dir,
            candidate_revision="37.1.11",
            projection_sha256="64f3ddd82cc72dacc9146e492345d1f7db8196cff053d7343521021140a7404e",
            repo_sha="8570a837852a2ab669092ac3940086a1fdc1cb81",
            run_id="35676154497",
            observed_at="2026-09-22T01:32:53Z",
            raw_help_file=self.raw_help_file,
            raw_help_gpu_file=self.raw_help_gpu_file,
        )
        self.assertEqual(exit_code, 0)
        self.assertTrue(gpu_ev["evidence_ready"])
        self.assertEqual(gpu_ev["status"], "PASS_STRICT")

        # Check files exist
        json_path = os.path.join(self.out_dir, "gpu-evidence.json")
        txt_path = os.path.join(self.out_dir, "gpu-evidence.txt")
        chk_path = os.path.join(self.out_dir, "checksums.sha256")
        self.assertTrue(os.path.isfile(json_path))
        self.assertTrue(os.path.isfile(txt_path))
        self.assertTrue(os.path.isfile(chk_path))

        # Check raw files are NOT present
        self.assertFalse(os.path.exists(os.path.join(self.out_dir, "raw_gpu_output.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.out_dir, "raw_help.txt")))

        # Check canonical JSON match
        with open(json_path, "rb") as f:
            bytes_on_disk = f.read()
        self.assertEqual(bytes_on_disk, canonicalize_json_v1(gpu_ev))
        disk_sha = hashlib.sha256(bytes_on_disk).hexdigest()
        self.assertEqual(disk_sha, ev_sha)

        # Check checksums file content
        with open(chk_path, "r", encoding="utf-8") as f:
            chk_lines = f.readlines()
        self.assertEqual(len(chk_lines), 2)
        self.assertTrue(chk_lines[0].startswith(disk_sha))
        self.assertTrue(chk_lines[0].endswith("gpu-evidence.json\n"))


if __name__ == "__main__":
    unittest.main()
