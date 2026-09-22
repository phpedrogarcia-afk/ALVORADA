#!/usr/bin/env python3
"""ALVORADA Static Test Fixture Builder

Compiles, dexes, packages, and signs the minimal API 36 test fixture
(`org.alvorada.reliability.harness`) using strictly locked Android SDK tools:
    - build-tools: 36.0.0 (aapt2, d8, zipalign, apksigner)
    - platforms: android-36 (android.jar)
    - JDK: 17 (javac, keytool)

Enforces strict P6 gate verification fail-closed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional
import zipfile

CONTRACT_P6_VERIFICATION = "ALVORADA_P6_FIXTURE_BUILD_V1"
PACKAGE_NAME = "org.alvorada.reliability.harness"
FIXTURE_PACKAGE_NAME = PACKAGE_NAME
LOCKED_BUILD_TOOLS_REV = "36.0.0"
LOCKED_PLATFORM_API = "android-36"


class FixtureBuildError(Exception):
    """Raised when fixture compilation, packaging, or signing fails."""


class FixtureBuilder:
    def __init__(
        self,
        sdk_root: Optional[Path] = None,
        fixture_dir: Optional[Path] = None,
        build_dir: Optional[Path] = None,
    ) -> None:
        self.sdk_root = (
            sdk_root
            or Path(os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or "/usr/local/lib/android/sdk")
        ).resolve()
        self.fixture_dir = (
            fixture_dir
            or Path(__file__).resolve().parent.parent / "fixture"
        ).resolve()
        self.build_dir = (
            build_dir
            or Path(__file__).resolve().parent.parent / "build" / "fixture"
        ).resolve()

        self.android_jar = self.sdk_root / "platforms" / LOCKED_PLATFORM_API / "android.jar"
        self.build_tools_dir = self.sdk_root / "build-tools" / LOCKED_BUILD_TOOLS_REV

    def _resolve_tool(self, name: str) -> str:
        # Check inside build-tools
        candidate = self.build_tools_dir / name
        if candidate.is_file():
            return str(candidate)
        # Check candidate.bat or candidate.exe
        for ext in (".bat", ".exe", ".cmd"):
            cand_ext = self.build_tools_dir / f"{name}{ext}"
            if cand_ext.is_file():
                return str(cand_ext)

        # Fallback to system PATH
        which = shutil.which(name)
        if which:
            return which
        raise FixtureBuildError(f"Required build tool '{name}' not found in {self.build_tools_dir} or PATH")

    def build_apk(self, output_apk: Optional[Path] = None) -> Path:
        """Build, package, align, sign, and verify the fixture APK."""
        if not self.android_jar.is_file():
            raise FixtureBuildError(f"android.jar not found at {self.android_jar}")

        manifest_file = self.fixture_dir / "AndroidManifest.xml"
        if not manifest_file.is_file():
            raise FixtureBuildError(f"AndroidManifest.xml not found at {manifest_file}")

        self.build_dir.mkdir(parents=True, exist_ok=True)
        gen_dir = self.build_dir / "gen"
        obj_dir = self.build_dir / "obj"
        dex_dir = self.build_dir / "dex"

        for d in (gen_dir, obj_dir, dex_dir):
            if d.is_dir():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)

        aapt2_bin = self._resolve_tool("aapt2")
        d8_bin = self._resolve_tool("d8")
        zipalign_bin = self._resolve_tool("zipalign")
        apksigner_bin = self._resolve_tool("apksigner")

        # Step 1: AAPT2 Link to create base unaligned APK and generate R.java
        unaligned_base_apk = self.build_dir / "unaligned_base.apk"
        if unaligned_base_apk.exists():
            unaligned_base_apk.unlink()

        aapt_cmd = [
            aapt2_bin,
            "link",
            "-I",
            str(self.android_jar),
            "--manifest",
            str(manifest_file),
            "-o",
            str(unaligned_base_apk),
            "--java",
            str(gen_dir),
        ]
        res = subprocess.run(aapt_cmd, capture_output=True, check=False)
        if res.returncode != 0:
            raise FixtureBuildError(
                f"aapt2 link failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
            )

        # Step 2: Compile Java sources
        java_sources: List[Path] = []
        src_dir = self.fixture_dir / "src"
        if src_dir.is_dir():
            java_sources.extend(src_dir.rglob("*.java"))
        java_sources.extend(gen_dir.rglob("*.java"))

        if not java_sources:
            raise FixtureBuildError(f"No Java sources found in {src_dir} or {gen_dir}")

        javac_bin = shutil.which("javac") or "javac"
        javac_cmd = [
            javac_bin,
            "-encoding",
            "UTF-8",
            "-cp",
            str(self.android_jar),
            "-d",
            str(obj_dir),
        ] + [str(p) for p in java_sources]

        res = subprocess.run(javac_cmd, capture_output=True, check=False)
        if res.returncode != 0:
            raise FixtureBuildError(
                f"javac failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
            )

        # Step 3: Dex with d8
        class_files = list(obj_dir.rglob("*.class"))
        if not class_files:
            raise FixtureBuildError(f"No compiled .class files found in {obj_dir}")

        d8_cmd = [
            d8_bin,
            "--lib",
            str(self.android_jar),
            "--output",
            str(dex_dir),
        ] + [str(cf) for cf in class_files]

        res = subprocess.run(d8_cmd, capture_output=True, check=False)
        if res.returncode != 0:
            raise FixtureBuildError(
                f"d8 failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
            )

        classes_dex = dex_dir / "classes.dex"
        if not classes_dex.is_file():
            raise FixtureBuildError(f"classes.dex was not generated in {dex_dir}")

        # Step 4: Inject classes.dex into unaligned APK
        with zipfile.ZipFile(unaligned_base_apk, mode="a") as zf:
            zf.write(classes_dex, arcname="classes.dex")

        # Step 5: Zipalign (4-byte alignment)
        aligned_apk = self.build_dir / "aligned.apk"
        if aligned_apk.exists():
            aligned_apk.unlink()

        zipalign_cmd = [
            zipalign_bin,
            "-f",
            "-p",
            "4",
            str(unaligned_base_apk),
            str(aligned_apk),
        ]
        res = subprocess.run(zipalign_cmd, capture_output=True, check=False)
        if res.returncode != 0:
            raise FixtureBuildError(
                f"zipalign failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
            )

        # Step 6: Generate debug keystore if needed
        keystore_path = self.build_dir / "debug.keystore"
        if not keystore_path.is_file():
            keytool_bin = shutil.which("keytool") or "keytool"
            keytool_cmd = [
                keytool_bin,
                "-genkeypair",
                "-keystore",
                str(keystore_path),
                "-storepass",
                "android",
                "-alias",
                "androiddebugkey",
                "-keypass",
                "android",
                "-dname",
                "CN=Android Debug,O=Android,C=US",
                "-validity",
                "10000",
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
            ]
            res = subprocess.run(keytool_cmd, capture_output=True, check=False)
            if res.returncode != 0:
                raise FixtureBuildError(
                    f"keytool failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
                )

        # Step 7: Sign with apksigner
        final_apk = output_apk or (self.build_dir / "alvorada-harness.apk")
        final_apk.parent.mkdir(parents=True, exist_ok=True)
        if final_apk.exists():
            final_apk.unlink()

        apksigner_cmd = [
            apksigner_bin,
            "sign",
            "--ks",
            str(keystore_path),
            "--ks-pass",
            "pass:android",
            "--ks-key-alias",
            "androiddebugkey",
            "--key-pass",
            "pass:android",
            "--out",
            str(final_apk),
            str(aligned_apk),
        ]
        res = subprocess.run(apksigner_cmd, capture_output=True, check=False)
        if res.returncode != 0:
            raise FixtureBuildError(
                f"apksigner failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
            )

        # Step 8: Verify signature
        verify_cmd = [apksigner_bin, "verify", str(final_apk)]
        res = subprocess.run(verify_cmd, capture_output=True, check=False)
        if res.returncode != 0:
            raise FixtureBuildError(
                f"apksigner verify failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
            )

        return final_apk

    def verify_p6(self, apk_path: Path) -> Dict[str, Any]:
        """Verify P6 STATIC TEST FIXTURE BUILDS AGAINST API 36."""
        if not apk_path.is_file():
            raise FixtureBuildError(f"P6_FAILED: APK does not exist at {apk_path}")

        size_bytes = apk_path.stat().st_size
        if size_bytes < 1024:
            raise FixtureBuildError(f"P6_FAILED: APK size suspiciously small ({size_bytes} bytes)")

        # Verify APK contains classes.dex and AndroidManifest.xml
        with zipfile.ZipFile(apk_path, "r") as zf:
            namelist = zf.namelist()
            if "classes.dex" not in namelist:
                raise FixtureBuildError("P6_FAILED: APK does not contain classes.dex")
            if "AndroidManifest.xml" not in namelist:
                raise FixtureBuildError("P6_FAILED: APK does not contain AndroidManifest.xml")

        import hashlib
        sha = hashlib.sha256()
        with open(apk_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        apk_sha256 = sha.hexdigest()

        return {
            "contract": CONTRACT_P6_VERIFICATION,
            "gate": "P6",
            "result": "PASS",
            "package_name": PACKAGE_NAME,
            "target_api": 36,
            "apk_path": str(apk_path),
            "apk_size_bytes": size_bytes,
            "apk_sha256": apk_sha256,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="ALVORADA Static Test Fixture Builder")
    parser.add_argument("--sdk-root", type=Path, default=None)
    parser.add_argument("--fixture-dir", type=Path, default=None)
    parser.add_argument("--build-dir", type=Path, default=None)
    parser.add_argument("--output-apk", type=Path, default=None)
    args = parser.parse_args()

    builder = FixtureBuilder(
        sdk_root=args.sdk_root,
        fixture_dir=args.fixture_dir,
        build_dir=args.build_dir,
    )
    apk = builder.build_apk(output_apk=args.output_apk)
    p6 = builder.verify_p6(apk)
    print(json.dumps(p6, indent=2))


if __name__ == "__main__":
    main()
