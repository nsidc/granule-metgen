#!/usr/bin/env python3
"""
Command-line interface for polygon generation and CMR comparison.

This is a wrapper around polygon_driver.py that can be used as a standalone CLI
or integrated into the main MetGenC CLI.
"""

import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from polygon_driver import main

if __name__ == "__main__":
    main()