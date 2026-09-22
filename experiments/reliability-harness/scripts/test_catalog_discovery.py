#!/usr/bin/env python3
"""
ALVORADA — Test Suite Entrypoint for Catalog Discovery & Core Contracts
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_tests(loader, tests, pattern):
    """Avoid duplicate test discovery when using unittest discover."""
    return unittest.TestSuite()


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for mod_name in ["test_catalog_core", "test_catalog_lock_model", "test_catalog_discovery_runner"]:
        mod = __import__(mod_name)
        suite.addTests(loader.loadTestsFromModule(mod))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
