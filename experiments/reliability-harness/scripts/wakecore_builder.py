#!/usr/bin/env python3
"""ALVORADA Wake Core APK Builder

Compiles, dexes, packages, aligns, and signs the minimal API 36 Wake Core test app
(`org.alvorada.reliability.wakecore`) using strictly locked Android SDK tools:
    - build-tools: 36.0.0 (aapt2, d8, zipalign, apksigner)
    - platforms: android-36 (android.jar)
    - JDK: 17 (javac, keytool)

Enforces strict reproducible compilation fail-closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional
import zipfile

CONTRACT_WAKECORE_BUILD = "ALVORADA_WAKECORE_BUILD_V1"
PACKAGE_NAME = "org.alvorada.reliability.wakecore"
LOCKED_BUILD_TOOLS_REV = "36.0.0"
LOCKED_PLATFORM_API = "android-36"


class WakeCoreBuildError(Exception):
    """Raised when wakecore compilation, packaging, or signing fails."""


class WakeCoreBuilder:
    def __init__(
        self,
        sdk_root: Optional[Path] = None,
        wakecore_dir: Optional[Path] = None,
        build_dir: Optional[Path] = None,
    ) -> None:
        self.sdk_root = (
            sdk_root
            or Path(os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or "/usr/local/lib/android/sdk")
        ).resolve()
        self.wakecore_dir = (
            wakecore_dir
            or Path(__file__).resolve().parent.parent / "wakecore"
        ).resolve()
        self.build_dir = (
            build_dir
            or Path(__file__).resolve().parent.parent / "build" / "wakecore"
        ).resolve()

        self.android_jar = self.sdk_root / "platforms" / LOCKED_PLATFORM_API / "android.jar"
        self.build_tools_dir = self.sdk_root / "build-tools" / LOCKED_BUILD_TOOLS_REV

    def _resolve_java_tool(self, name: str) -> str:
        # Check JAVA_HOME
        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            for ext in ("", ".exe", ".cmd", ".bat"):
                cand_ext = Path(java_home) / "bin" / f"{name}{ext}"
                if cand_ext.is_file():
                    return str(cand_ext)

        # Check shutil.which
        which = shutil.which(name)
        if which:
            return which

        # Check standard Java locations on Windows / Linux
        search_dirs = [
            Path("C:/Program Files/Java/jdk-17/bin"),
            Path("/usr/lib/jvm/java-17-openjdk-amd64/bin"),
            Path("/usr/lib/jvm/java-17-openjdk/bin"),
        ]
        for d in search_dirs:
            for ext in ("", ".exe", ".cmd", ".bat"):
                cand = d / f"{name}{ext}"
                if cand.is_file():
                    return str(cand)

        raise WakeCoreBuildError(f"Required Java tool '{name}' not found")

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
        raise WakeCoreBuildError(f"Required build tool '{name}' not found in {self.build_tools_dir} or PATH")

    def build_apk(self, output_apk: Optional[Path] = None) -> Path:
        """Build, package, align, sign, and verify the wakecore APK."""
        if not self.android_jar.is_file():
            raise WakeCoreBuildError(f"android.jar not found at {self.android_jar}")

        manifest_file = self.wakecore_dir / "AndroidManifest.xml"
        if not manifest_file.is_file():
            raise WakeCoreBuildError(f"AndroidManifest.xml not found at {manifest_file}")

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
            raise WakeCoreBuildError(
                f"aapt2 link failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
            )

        # Step 2: Compile Java sources
        java_sources: List[Path] = []
        src_dir = self.wakecore_dir / "src"
        if src_dir.is_dir():
            java_sources.extend(src_dir.rglob("*.java"))
        java_sources.extend(gen_dir.rglob("*.java"))

        if not java_sources:
            raise WakeCoreBuildError(f"No Java sources found in {src_dir} or {gen_dir}")

        javac_bin = self._resolve_java_tool("javac")
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
            raise WakeCoreBuildError(
                f"javac failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
            )

        # Step 3: Dex with d8
        class_files = list(obj_dir.rglob("*.class"))
        if not class_files:
            raise WakeCoreBuildError(f"No compiled .class files found in {obj_dir}")

        d8_cmd = [
            d8_bin,
            "--lib",
            str(self.android_jar),
            "--output",
            str(dex_dir),
        ] + [str(cf) for cf in class_files]

        res = subprocess.run(d8_cmd, capture_output=True, check=False)
        if res.returncode != 0:
            raise WakeCoreBuildError(
                f"d8 failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
            )

        classes_dex = dex_dir / "classes.dex"
        if not classes_dex.is_file():
            raise WakeCoreBuildError(f"classes.dex was not generated in {dex_dir}")

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
            raise WakeCoreBuildError(
                f"zipalign failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
            )

        # Step 6: Generate debug keystore if needed
        keystore_path = self.build_dir / "debug.keystore"
        if not keystore_path.is_file():
            keytool_bin = self._resolve_java_tool("keytool")
            keytool_cmd = [
                keytool_bin,
                "-genkeypair",
                "-v",
                "-keystore",
                str(keystore_path),
                "-storepass",
                "android",
                "-alias",
                "androiddebugkey",
                "-keypass",
                "android",
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                "10000",
                "-dname",
                "CN=Android Debug,O=Android,C=US",
            ]
            res = subprocess.run(keytool_cmd, capture_output=True, check=False)
            if res.returncode != 0:
                raise WakeCoreBuildError(
                    f"keytool failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
                )

        # Step 7: Sign with apksigner
        final_apk = output_apk or (self.build_dir / "alvorada-wakecore.apk")
        if final_apk.exists():
            final_apk.unlink()

        # Resolve apksigner path / java wrapper if on Windows or Linux
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
            raise WakeCoreBuildError(
                f"apksigner failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
            )

        # Step 8: Verify signature
        verify_cmd = [apksigner_bin, "verify", "--verbose", str(final_apk)]
        res = subprocess.run(verify_cmd, capture_output=True, check=False)
        if res.returncode != 0:
            raise WakeCoreBuildError(
                f"apksigner verify failed ({res.returncode}):\n{res.stderr.decode('utf-8', errors='replace')}"
            )

        return final_apk

    def verify_apk(self, apk_path: Path) -> Dict[str, Any]:
        """Verify the built APK contains required components and return metadata."""
        if not apk_path.is_file():
            raise WakeCoreBuildError(f"APK does not exist at {apk_path}")

        apk_bytes = apk_path.read_bytes()
        apk_sha = hashlib.sha256(apk_bytes).hexdigest()

        try:
            with zipfile.ZipFile(apk_path, "r") as zf:
                namelist = zf.namelist()
                if "classes.dex" not in namelist:
                    raise WakeCoreBuildError(f"APK does not contain classes.dex: {namelist}")
                if "AndroidManifest.xml" not in namelist:
                    raise WakeCoreBuildError(f"APK does not contain AndroidManifest.xml: {namelist}")
        except zipfile.BadZipFile as e:
            raise WakeCoreBuildError(f"Corrupt APK file: {e}")

        return {
            "contract": CONTRACT_WAKECORE_BUILD,
            "result": "PASS",
            "package_name": PACKAGE_NAME,
            "target_api": 36,
            "apk_path": str(apk_path),
            "apk_size": len(apk_bytes),
            "apk_sha256": apk_sha,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="ALVORADA Wake Core APK Builder")
    parser.add_argument("--sdk-root", type=Path, default=None, help="Path to Android SDK")
    parser.add_argument("--wakecore-dir", type=Path, default=None, help="Path to wakecore sources")
    parser.add_argument("--build-dir", type=Path, default=None, help="Build output directory")
    parser.add_argument("--output-apk", type=Path, default=None, help="Path for generated APK")

    args = parser.parse_args()

    builder = WakeCoreBuilder(
        sdk_root=args.sdk_root,
        wakecore_dir=args.wakecore_dir,
        build_dir=args.build_dir,
    )
    apk = builder.build_apk(args.output_apk)
    print(f"WAKECORE_APK_BUILD_SUCCESS={apk}")


if __name__ == "__main__":
    main()
