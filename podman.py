#!/usr/bin/env python3
"""Thin entry point for the podman sandbox CLI."""

import sys
from src.logic.dependencies import check_podman_dependencies, print_missing_dependencies

missing = check_podman_dependencies()
if missing:
    print_missing_dependencies(missing)
    sys.exit(1)

from src.ui.podman_cli import main

sys.exit(main())
