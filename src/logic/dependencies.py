"""
Dependency checking and distro detection for the sandbox.

Detects the host Linux distribution and verifies that required
dependencies (podman, fuse-overlayfs, python3) are installed.
"""

import os
import shutil
import subprocess
from typing import Optional


DISTRO_INFO: dict = {}


def detect_distro() -> dict:
    """Detect the host Linux distribution.

    Reads /etc/os-release and returns a dict with distribution info.

    Returns:
        Dict with keys: id, name, pretty_name, version_id, is_debian,
        is_fedora, is_ubuntu.
    """
    global DISTRO_INFO
    if DISTRO_INFO:
        return DISTRO_INFO

    distro = {
        "id": "unknown",
        "name": "Unknown",
        "pretty_name": "Unknown",
        "version_id": "",
        "is_debian": False,
        "is_ubuntu": False,
        "is_fedora": False,
        "package_manager": None,
    }

    os_release_path = "/etc/os-release"
    if os.path.exists(os_release_path):
        with open(os_release_path, "r") as f:
            for line in f:
                line = line.strip()
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                value = value.strip('"')
                if key == "ID":
                    distro["id"] = value
                elif key == "NAME":
                    distro["name"] = value
                elif key == "PRETTY_NAME":
                    distro["pretty_name"] = value
                elif key == "VERSION_ID":
                    distro["version_id"] = value

    distro["is_debian"] = distro["id"] in ("debian", "raspbian")
    distro["is_ubuntu"] = distro["id"] == "ubuntu"
    distro["is_fedora"] = distro["id"] in ("fedora", "centos", "rhel", "rocky", "almalinux")

    if distro["is_debian"] or distro["is_ubuntu"]:
        distro["package_manager"] = "apt"
    elif distro["is_fedora"]:
        distro["package_manager"] = "dnf"

    DISTRO_INFO = distro
    return distro


def _check_command(name: str) -> bool:
    """Check if a command is available on the system.

    Args:
        name: Command name to look for.

    Returns:
        True if the command is found in PATH.
    """
    return shutil.which(name) is not None


def check_dependencies(required: list[str]) -> list[str]:
    """Check that all required dependencies are installed.

    Args:
        required: List of command names to check for.

    Returns:
        List of missing dependency names. Empty if all present.
    """
    missing = []
    for dep in required:
        if not _check_command(dep):
            missing.append(dep)
    return missing


def check_cli_dependencies() -> list[str]:
    """Check dependencies for the Python shell sandbox (cli.py).

    Returns:
        List of missing dependencies.
    """
    return check_dependencies(["python3", "fuse-overlayfs"])


def check_podman_dependencies() -> list[str]:
    """Check dependencies for the podman sandbox (podman.py).

    Returns:
        List of missing dependencies.
    """
    return check_dependencies(["python3", "podman", "fuse-overlayfs"])


def install_instructions(missing: list[str]) -> str:
    """Return installation instructions for missing dependencies.

    Args:
        missing: List of missing dependency names.

    Returns:
        Formatted installation command string.
    """
    distro = detect_distro()
    pm = distro["package_manager"]

    instructions: list[str] = []

    if pm == "apt":
        cmd = "sudo apt-get install -y"
        for dep in missing:
            if dep == "python3":
                instructions.append(f"  {cmd} python3")
            elif dep == "fuse-overlayfs":
                instructions.append(f"  {cmd} fuse-overlayfs")
            elif dep == "podman":
                instructions.append(f"  {cmd} podman")
            else:
                instructions.append(f"  {cmd} {dep}")
    elif pm == "dnf":
        cmd = "sudo dnf install -y"
        for dep in missing:
            if dep == "python3":
                instructions.append(f"  {cmd} python3")
            elif dep == "fuse-overlayfs":
                instructions.append(f"  {cmd} fuse-overlayfs")
            elif dep == "podman":
                instructions.append(f"  {cmd} podman")
            else:
                instructions.append(f"  {cmd} {dep}")
    else:
        for dep in missing:
            instructions.append(f"  Install {dep} using your distribution's package manager")

    return "\n".join(instructions)


def print_missing_dependencies(missing: list[str]) -> None:
    """Print a formatted error message for missing dependencies.

    Args:
        missing: List of missing dependency names.
    """
    if not missing:
        return

    distro = detect_distro()
    print(f"\nThe following required dependencies are missing on {distro['pretty_name']}:")
    for dep in missing:
        print(f"  X {dep}")
    print()
    print("Install them with:")
    print(install_instructions(missing))
    print()
