#!/usr/bin/env python3
"""
ALVORADA — Catalog Discovery Module Entrypoint
Re-exports core contracts from catalog_core.py for RECOVERY-G1-001.
"""

import sys
import os

# Ensure local imports resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog_core import (
    CANONICAL_JSON_CONTRACT,
    MIN_SAFE_INTEGER,
    MAX_SAFE_INTEGER,
    validate_canonical_timestamp,
    validate_canonical_data,
    escape_canonical_string,
    serialize_canonical_json_v1,
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
    main,
)

if __name__ == "__main__":
    main()
