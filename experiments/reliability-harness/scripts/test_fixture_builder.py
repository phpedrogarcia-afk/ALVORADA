from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple
import unittest
from unittest.mock import MagicMock, patch
import zipfile

from fixture_builder import (
    FIXTURE_PACKAGE_NAME,
    CONTRACT_P6_VERIFICATION,
    FixtureBuilder,
    FixtureBuildError,
)


class TestFixtureBuilder(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.sdk_root = self.root / "sdk"
        self.fixture_dir = self.root / "fixture"
        self.build_dir = self.root / "build"

        self.sdk_root.mkdir(parents=True, exist_ok=True)
        self.fixture_dir.mkdir(parents=True, exist_ok=True)
        self.build_dir.mkdir(parents=True, exist_ok=True)

        # Setup mock platform android.jar
        self.plat_dir = self.sdk_root / "platforms" / "android-36"
        self.plat_dir.mkdir(parents=True, exist_ok=True)
        (self.plat_dir / "android.jar").write_bytes(b"mock_android_jar")

        # Setup mock build-tools
        self.bt_dir = self.sdk_root / "build-tools" / "36.0.0"
        self.bt_dir.mkdir(parents=True, exist_ok=True)
        for t in ("aapt2", "d8", "zipalign", "apksigner"):
            (self.bt_dir / t).write_bytes(b"mock_binary")

        # Setup mock manifest and source
        (self.fixture_dir / "AndroidManifest.xml").write_text("<manifest></manifest>")
        src_pkg = self.fixture_dir / "src" / "org" / "alvorada" / "reliability" / "harness"
        src_pkg.mkdir(parents=True, exist_ok=True)
        (src_pkg / "HarnessReceiver.java").write_text("package org.alvorada.reliability.harness; class HarnessReceiver {}")

        self.builder = FixtureBuilder(
            sdk_root=self.sdk_root,
            fixture_dir=self.fixture_dir,
            build_dir=self.build_dir,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_missing_android_jar_raises(self) -> None:
        (self.plat_dir / "android.jar").unlink()
        with self.assertRaises(FixtureBuildError) as ctx:
            self.builder.build_apk()
        self.assertIn("android.jar not found", str(ctx.exception))

    def test_missing_manifest_raises(self) -> None:
        (self.fixture_dir / "AndroidManifest.xml").unlink()
        with self.assertRaises(FixtureBuildError) as ctx:
            self.builder.build_apk()
        self.assertIn("AndroidManifest.xml not found", str(ctx.exception))

    def test_verify_p6_missing_apk_raises(self) -> None:
        missing = self.build_dir / "non_existent.apk"
        with self.assertRaises(FixtureBuildError) as ctx:
            self.builder.verify_p6(missing)
        self.assertIn("APK does not exist", str(ctx.exception))

    def test_verify_p6_missing_classes_dex_raises(self) -> None:
        corrupt_apk = self.build_dir / "no_dex.apk"
        with zipfile.ZipFile(corrupt_apk, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"manifest_data" * 100)
        with self.assertRaises(FixtureBuildError) as ctx:
            self.builder.verify_p6(corrupt_apk)
        self.assertIn("does not contain classes.dex", str(ctx.exception))

    def test_verify_p6_success(self) -> None:
        valid_apk = self.build_dir / "valid.apk"
        with zipfile.ZipFile(valid_apk, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"manifest_data" * 100)
            zf.writestr("classes.dex", b"dex_bytecode" * 100)

        res = self.builder.verify_p6(valid_apk)
        self.assertEqual(res["gate"], "P6")
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(res["package_name"], FIXTURE_PACKAGE_NAME)
        self.assertEqual(res["target_api"], 36)
        self.assertTrue(len(res["apk_sha256"]) == 64)

    @patch("subprocess.run")
    def test_build_apk_end_to_end_mocked(self, mock_run: MagicMock) -> None:
        def side_effect(cmd, *args, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "aapt2 link" in cmd_str:
                unaligned = self.build_dir / "unaligned_base.apk"
                with zipfile.ZipFile(unaligned, "w") as zf:
                    zf.writestr("AndroidManifest.xml", b"mock_manifest" * 200)
                gen = self.build_dir / "gen" / "R.java"
                gen.parent.mkdir(parents=True, exist_ok=True)
                gen.write_text("class R {}")
                return MagicMock(returncode=0, stdout=b"", stderr=b"")

            elif "javac" in cmd_str:
                obj = self.build_dir / "obj" / "HarnessReceiver.class"
                obj.parent.mkdir(parents=True, exist_ok=True)
                obj.write_bytes(b"mock_bytecode" * 100)
                return MagicMock(returncode=0, stdout=b"", stderr=b"")

            elif "d8" in cmd_str:
                dex = self.build_dir / "dex" / "classes.dex"
                dex.parent.mkdir(parents=True, exist_ok=True)
                dex.write_bytes(b"mock_dex" * 200)
                return MagicMock(returncode=0, stdout=b"", stderr=b"")

            elif "zipalign" in cmd_str:
                aligned = self.build_dir / "aligned.apk"
                # Copy from unaligned
                shutil.copy(self.build_dir / "unaligned_base.apk", aligned)
                return MagicMock(returncode=0, stdout=b"", stderr=b"")

            elif "keytool" in cmd_str:
                ks = self.build_dir / "debug.keystore"
                ks.write_bytes(b"mock_keystore")
                return MagicMock(returncode=0, stdout=b"", stderr=b"")

            elif "apksigner sign" in cmd_str:
                out_apk = self.build_dir / "alvorada-harness.apk"
                shutil.copy(self.build_dir / "aligned.apk", out_apk)
                return MagicMock(returncode=0, stdout=b"", stderr=b"")

            elif "apksigner verify" in cmd_str:
                return MagicMock(returncode=0, stdout=b"VERIFIED", stderr=b"")

            return MagicMock(returncode=0, stdout=b"", stderr=b"")

        mock_run.side_effect = side_effect
        apk = self.builder.build_apk()
        self.assertTrue(apk.is_file())

        p6 = self.builder.verify_p6(apk)
        self.assertEqual(p6["result"], "PASS")


if __name__ == "__main__":
    unittest.main()
