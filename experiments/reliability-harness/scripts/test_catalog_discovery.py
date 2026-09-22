#!/usr/bin/env python3
"""
ALVORADA — Test Suite Entrypoint for Catalog Discovery & Core Contracts
Re-exports and runs tests from test_catalog_core.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_catalog_core import *
from test_catalog_lock_model import *
from test_catalog_discovery_runner import *

if __name__ == "__main__":
    unittest.main()
