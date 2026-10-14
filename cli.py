#!/usr/bin/env python3
"""Thin entry point for the sandbox CLI."""

import sys
from src.logic.dependencies import check_cli_dependencies, print_missing_dependencies

missing = check_cli_dependencies()
if missing:
    print_missing_dependencies(missing)
    sys.exit(1)

from src.ui.cli_app import main

sys.exit(main())
