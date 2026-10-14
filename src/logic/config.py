"""
Configuration loader for the sandbox.

Reads .env file (if present) for runtime overrides.
Falls back to built-in defaults if .env is absent.
"""

import os
from typing import Optional


try:
    from dotenv import load_dotenv
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_IMAGE = "docker.io/library/python:latest"
_DEFAULT_SANDBOX_NAME = "sandbox"
_DEFAULT_PROJECT_DIR = os.path.join(_PROJECT_ROOT, "project")


def _load_env() -> None:
    """Load .env file from project root if it exists."""
    if _DOTENV_AVAILABLE:
        env_path = os.path.join(_PROJECT_ROOT, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)


_load_env()


def get_default_image() -> str:
    """Get the default container image.

    Returns:
        Container image string, from .env or built-in default.
    """
    return os.environ.get("SANDBOX_CONTAINER_IMAGE", _DEFAULT_IMAGE)


def get_default_sandbox_name() -> str:
    """Get the default sandbox container name.

    Returns:
        Container name string.
    """
    return os.environ.get("SANDBOX_CONTAINER_NAME", _DEFAULT_SANDBOX_NAME)


def get_default_project_dir() -> str:
    """Get the default project directory.

    Returns:
        Absolute path to the project directory.
    """
    return os.environ.get("SANDBOX_PROJECT_DIR", _DEFAULT_PROJECT_DIR)
