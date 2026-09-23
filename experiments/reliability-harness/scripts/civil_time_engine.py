"""
Civil Time Engine for ALVORADA G1.

Implements and wraps the authoritative civil scheduling resolver:
1. Timezone changes preserve civil local clock time.
2. DST gap forwards to the first valid local time after the gap (DST_GAP_FORWARD).
3. DST fold chooses the first valid occurrence only (DST_FOLD_FIRST_OCCURRENCE).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


JAVA_RESOLVER_PATH = (
    Path(__file__).resolve().parent.parent
    / "wakecore"
    / "src"
    / "org"
    / "alvorada"
    / "reliability"
    / "wakecore"
    / "CivilScheduleResolver.java"
)


class CivilScheduleResolutionError(Exception):
    """Raised when civil schedule resolution fails."""


def resolve_civil_time(
    date_str: str,  # YYYY-MM-DD
    time_str: str,  # HH:MM:SS or HH:MM
    timezone_id: str,
) -> Dict[str, Any]:
    """
    Invokes the authoritative CivilScheduleResolver.
    Returns the structured resolution metadata.
    """
    if len(time_str.split(":")) == 2:
        time_str = f"{time_str}:00"

    cmd = ["java", str(JAVA_RESOLVER_PATH), date_str, time_str, timezone_id]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise CivilScheduleResolutionError(
            f"Civil schedule resolution failed for {date_str} {time_str} in {timezone_id}: {res.stderr}"
        )

    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError as err:
        raise CivilScheduleResolutionError(
            f"Failed to parse resolver JSON output: {res.stdout}"
        ) from err


def preserve_civil_time_on_tz_change(
    civil_time_str: str,  # "07:00"
    target_date_str: str,  # "2026-06-15"
    old_timezone_id: str,
    new_timezone_id: str,
) -> Dict[str, Any]:
    """
    Proves frozen policy:
    Alarm configured for civil_time_str (e.g. 07:00 local).
    When timezone changes from old_timezone_id to new_timezone_id,
    the next alarm remains civil_time_str in the new timezone, preserving civil clock time.
    """
    old_res = resolve_civil_time(target_date_str, civil_time_str, old_timezone_id)
    new_res = resolve_civil_time(target_date_str, civil_time_str, new_timezone_id)

    return {
        "civil_time": civil_time_str,
        "date": target_date_str,
        "old_timezone": old_timezone_id,
        "old_resolution": old_res,
        "new_timezone": new_timezone_id,
        "new_resolution": new_res,
        "civil_clock_preserved": (
            new_res["resolved_local"].split("T")[1][:5] == civil_time_str[:5]
        ),
    }
