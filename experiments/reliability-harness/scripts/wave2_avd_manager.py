#!/usr/bin/env python3
"""ALVORADA Wave 2 AVD Manager

Provides governed, observe-first creation and verification of the locked
API 36 experimental Android Virtual Device:
    alvorada_e1_api36_x86_64

Locked hardware specifications:
    - System image: system-images;android-36;default;x86_64
    - GPU mode: swiftshader
    - CPU cores: 2
    - RAM: 2048 MB
    - SD card: no
    - Camera: none
    - Play Store: false
    - Snapshot: disabled / cold-boot

Enforces strict P1 gate verification fail-closed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

AVD_NAME_DEFAULT = "alvorada_e1_api36_x86_64"
LOCKED_SYSTEM_IMAGE_PACKAGE = "system-images;android-36;default;x86_64"
LOCKED_GPU_MODE = "swiftshader"
LOCKED_CPU_CORES = 2
LOCKED_RAM_MB = 2048

CONTRACT_P1_VERIFICATION = "ALVORADA_P1_AVD_CONFIG_V1"


class AvdInspectionError(Exception):
    """Raised when AVD inspection or validation fails."""


def get_default_avd_home() -> Path:
    """Resolve the directory where AVDs and .ini descriptors are stored."""
    if "ANDROID_AVD_HOME" in os.environ and os.environ["ANDROID_AVD_HOME"]:
        return Path(os.environ["ANDROID_AVD_HOME"]).expanduser().resolve()
    return (Path.home() / ".android" / "avd").resolve()


def parse_ini_file(path: Path) -> Dict[str, str]:
    """Parse a standard Android ini configuration file into key-value pairs."""
    if not path.is_file():
        raise AvdInspectionError(f"INI file does not exist: {path}")
    data: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                data[key.strip()] = val.strip()
    return data


def write_ini_file(path: Path, data: Dict[str, str]) -> None:
    """Write or update key-value pairs in an Android ini configuration file."""
    existing: Dict[str, str] = {}
    if path.is_file():
        existing = parse_ini_file(path)
    existing.update(data)
    with open(path, "w", encoding="utf-8") as f:
        for k in sorted(existing.keys()):
            f.write(f"{k}={existing[k]}\n")


class Wave2AvdManager:
    """Manages creation, inspection, hardware tuning, and P1 verification of the locked AVD."""

    def __init__(
        self,
        sdk_root: Optional[Path] = None,
        avd_home: Optional[Path] = None,
        avd_name: str = AVD_NAME_DEFAULT,
    ) -> None:
        self.sdk_root = (
            sdk_root
            or Path(os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or "/usr/local/lib/android/sdk")
        ).resolve()
        self.avd_home = (avd_home or get_default_avd_home()).resolve()
        self.avd_name = avd_name

    def get_avd_descriptor_ini(self) -> Path:
        return self.avd_home / f"{self.avd_name}.ini"

    def get_avd_directory(self) -> Path:
        descriptor_ini = self.get_avd_descriptor_ini()
        if descriptor_ini.is_file():
            parsed = parse_ini_file(descriptor_ini)
            if "path" in parsed:
                return Path(parsed["path"]).resolve()
        return self.avd_home / f"{self.avd_name}.avd"

    def inspect_existing_avd(self) -> Tuple[str, Optional[Dict[str, str]], Optional[str]]:
        """Determine whether the AVD exists and whether its configuration matches the lock.

        Returns:
            (status, config_dict_or_none, mismatch_reason_or_none)
            status is one of: "ABSENT", "MATCH", "MISMATCH"
        """
        descriptor_ini = self.get_avd_descriptor_ini()
        if not descriptor_ini.is_file():
            return "ABSENT", None, "Descriptor .ini does not exist in AVD home"

        avd_dir = self.get_avd_directory()
        if not avd_dir.is_dir():
            return "MISMATCH", None, f"AVD directory does not exist: {avd_dir}"

        config_ini = avd_dir / "config.ini"
        if not config_ini.is_file():
            return "MISMATCH", None, f"config.ini does not exist in AVD directory: {config_ini}"

        config = parse_ini_file(config_ini)

        # Check image.sysdir.1
        sysdir = config.get("image.sysdir.1", "")
        expected_part = "system-images/android-36/default/x86_64"
        if expected_part not in sysdir.replace("\\", "/"):
            return "MISMATCH", config, f"image.sysdir.1 '{sysdir}' does not contain expected '{expected_part}'"

        # Check tag and abi
        tag_id = config.get("tag.id", "default")
        abi_type = config.get("abi.type", "")
        if abi_type != "x86_64":
            return "MISMATCH", config, f"abi.type '{abi_type}' != 'x86_64'"

        return "MATCH", config, None

    def delete_existing_avd_safely(self) -> None:
        """Safely delete only the campaign-owned AVD if it exists and needs recreation."""
        descriptor_ini = self.get_avd_descriptor_ini()
        avd_dir = self.get_avd_directory()

        if descriptor_ini.is_file():
            try:
                descriptor_ini.unlink()
            except OSError as err:
                raise AvdInspectionError(f"Failed to remove descriptor {descriptor_ini}: {err}") from err

        if avd_dir.is_dir():
            import shutil
            try:
                shutil.rmtree(avd_dir)
            except OSError as err:
                raise AvdInspectionError(f"Failed to remove AVD directory {avd_dir}: {err}") from err

    def create_avd(self, force_recreate: bool = False) -> Dict[str, Any]:
        """Create the AVD using avdmanager if absent or if recreation is required."""
        self.avd_home.mkdir(parents=True, exist_ok=True)
        status, config, reason = self.inspect_existing_avd()

        if status == "MATCH" and not force_recreate:
            # Already matches base creation, ensure hardware configuration is current
            self.configure_hardware_ini()
            return {
                "action": "REUSED_EXISTING",
                "avd_name": self.avd_name,
                "status": "READY",
            }

        if status == "MISMATCH" or force_recreate:
            self.delete_existing_avd_safely()

        # Locate avdmanager
        avdmanager_bin = self.sdk_root / "cmdline-tools" / "latest" / "bin" / "avdmanager"
        if not avdmanager_bin.is_file():
            # Search in cmdline-tools any version
            matches = list(self.sdk_root.glob("cmdline-tools/*/bin/avdmanager"))
            if matches:
                avdmanager_bin = matches[0]
            else:
                avdmanager_bin = Path("avdmanager")

        cmd = [
            str(avdmanager_bin),
            "create",
            "avd",
            "--name",
            self.avd_name,
            "--package",
            LOCKED_SYSTEM_IMAGE_PACKAGE,
            "--device",
            "pixel",
        ]

        # Execute creation with stdin 'no' (custom hardware profile prompt)
        res = subprocess.run(
            cmd,
            input=b"no\n",
            capture_output=True,
            check=False,
        )

        if res.returncode != 0:
            stderr_str = res.stderr.decode("utf-8", errors="replace")
            stdout_str = res.stdout.decode("utf-8", errors="replace")
            raise AvdInspectionError(
                f"avdmanager create avd failed (code {res.returncode}):\nSTDOUT: {stdout_str}\nSTDERR: {stderr_str}"
            )

        # Apply locked hardware parameters
        self.configure_hardware_ini()

        return {
            "action": "CREATED_NEW",
            "avd_name": self.avd_name,
            "status": "READY",
        }

    def configure_hardware_ini(self) -> None:
        """Write the strictly locked hardware parameters into config.ini."""
        avd_dir = self.get_avd_directory()
        config_ini = avd_dir / "config.ini"
        if not avd_dir.is_dir():
            raise AvdInspectionError(f"AVD directory {avd_dir} does not exist for hardware configuration")

        hardware_tuning = {
            "hw.cpu.ncore": str(LOCKED_CPU_CORES),
            "hw.ramSize": str(LOCKED_RAM_MB),
            "hw.gpu.enabled": "yes",
            "hw.gpu.mode": LOCKED_GPU_MODE,
            "hw.sdCard": "no",
            "hw.camera.back": "none",
            "hw.camera.front": "none",
            "PlayStore.enabled": "false",
            "fastboot.forceColdBoot": "yes",
            "vm.heapSize": "256",
        }
        write_ini_file(config_ini, hardware_tuning)

    def verify_p1(self) -> Dict[str, Any]:
        """Perform P1 AVD CONFIG VALID verification fail-closed.

        Checks:
            1. Descriptor .ini exists in AVD home.
            2. AVD directory exists.
            3. config.ini exists.
            4. hw.cpu.ncore is >= 2.
            5. hw.ramSize is >= 2048.
            6. hw.gpu.mode is swiftshader and hw.gpu.enabled is yes.
            7. image.sysdir.1 matches the locked system image.
            8. System image directory exists on disk and contains system files.

        Returns:
            Structured verification dictionary.
        """
        descriptor_ini = self.get_avd_descriptor_ini()
        if not descriptor_ini.is_file():
            raise AvdInspectionError(f"P1_FAILED: Descriptor INI missing at {descriptor_ini}")

        avd_dir = self.get_avd_directory()
        if not avd_dir.is_dir():
            raise AvdInspectionError(f"P1_FAILED: AVD directory missing at {avd_dir}")

        config_ini = avd_dir / "config.ini"
        if not config_ini.is_file():
            raise AvdInspectionError(f"P1_FAILED: config.ini missing at {config_ini}")

        config = parse_ini_file(config_ini)

        # 1. CPU cores
        try:
            cpu_cores = int(config.get("hw.cpu.ncore", "0"))
        except ValueError:
            raise AvdInspectionError(f"P1_FAILED: hw.cpu.ncore invalid: {config.get('hw.cpu.ncore')}")
        if cpu_cores < LOCKED_CPU_CORES:
            raise AvdInspectionError(
                f"P1_FAILED: hw.cpu.ncore ({cpu_cores}) is less than locked ({LOCKED_CPU_CORES})"
            )

        # 2. RAM size
        try:
            ram_mb = int(config.get("hw.ramSize", "0"))
        except ValueError:
            raise AvdInspectionError(f"P1_FAILED: hw.ramSize invalid: {config.get('hw.ramSize')}")
        if ram_mb < LOCKED_RAM_MB:
            raise AvdInspectionError(
                f"P1_FAILED: hw.ramSize ({ram_mb}) is less than locked ({LOCKED_RAM_MB})"
            )

        # 3. GPU mode
        gpu_mode = config.get("hw.gpu.mode", "")
        if gpu_mode != LOCKED_GPU_MODE:
            raise AvdInspectionError(
                f"P1_FAILED: hw.gpu.mode ('{gpu_mode}') does not match locked ('{LOCKED_GPU_MODE}')"
            )

        gpu_enabled = config.get("hw.gpu.enabled", "no")
        if gpu_enabled.lower() not in ("yes", "true", "1"):
            raise AvdInspectionError(f"P1_FAILED: hw.gpu.enabled is '{gpu_enabled}', expected 'yes'")

        # 4. System image directory
        sysdir = config.get("image.sysdir.1", "")
        expected_sysdir_part = "system-images/android-36/default/x86_64"
        if expected_sysdir_part not in sysdir.replace("\\", "/"):
            raise AvdInspectionError(
                f"P1_FAILED: image.sysdir.1 ('{sysdir}') does not match '{expected_sysdir_part}'"
            )

        # 5. Check actual disk existence of system image
        # sysdir could be relative to sdk_root or absolute
        resolved_sysdir = (self.sdk_root / sysdir) if not Path(sysdir).is_absolute() else Path(sysdir)
        if not resolved_sysdir.is_dir():
            # Try finding relative from sdk_root/system-images/...
            alt = self.sdk_root / "system-images" / "android-36" / "default" / "x86_64"
            if alt.is_dir():
                resolved_sysdir = alt
            else:
                raise AvdInspectionError(f"P1_FAILED: System image directory not found on disk: {resolved_sysdir}")

        # Check build.prop or system.img
        has_system_files = (
            (resolved_sysdir / "system.img").is_file()
            or (resolved_sysdir / "build.prop").is_file()
            or (resolved_sysdir / "source.properties").is_file()
        )
        if not has_system_files:
            raise AvdInspectionError(
                f"P1_FAILED: System image directory {resolved_sysdir} missing system.img/build.prop/source.properties"
            )

        return {
            "contract": CONTRACT_P1_VERIFICATION,
            "gate": "P1",
            "result": "PASS",
            "avd_name": self.avd_name,
            "system_image_package": LOCKED_SYSTEM_IMAGE_PACKAGE,
            "system_image_path": str(resolved_sysdir),
            "cpu_cores": cpu_cores,
            "ram_mb": ram_mb,
            "gpu_mode": gpu_mode,
            "descriptor_path": str(descriptor_ini),
            "config_path": str(config_ini),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="ALVORADA Wave 2 AVD Manager")
    parser.add_argument("--sdk-root", type=Path, default=None)
    parser.add_argument("--avd-home", type=Path, default=None)
    parser.add_argument("--avd-name", type=str, default=AVD_NAME_DEFAULT)
    parser.add_argument("--action", choices=["create", "inspect", "verify-p1"], default="verify-p1")
    parser.add_argument("--force", action="store_true", help="Force recreation of the AVD")

    args = parser.parse_args()
    mgr = Wave2AvdManager(sdk_root=args.sdk_root, avd_home=args.avd_home, avd_name=args.avd_name)

    if args.action == "inspect":
        status, config, reason = mgr.inspect_existing_avd()
        print(f"AVD_INSPECTION_STATUS: {status}")
        if reason:
            print(f"REASON: {reason}")
        if config:
            print(json.dumps(config, indent=2))
        sys.exit(0 if status == "MATCH" else 1)

    elif args.action == "create":
        res = mgr.create_avd(force_recreate=args.force)
        print(json.dumps(res, indent=2))
        # Follow by verify-p1
        p1 = mgr.verify_p1()
        print(json.dumps(p1, indent=2))
        sys.exit(0)

    elif args.action == "verify-p1":
        p1 = mgr.verify_p1()
        print(json.dumps(p1, indent=2))
        sys.exit(0)


if __name__ == "__main__":
    main()
