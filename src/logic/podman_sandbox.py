"""
Podman sandbox - ephemeral container-based shell for project experimentation.

Creates a podman container with a tmpfs-backed overlay mounted at the real
source path, and supports persistent state across multiple commands
within a session.
"""

import subprocess
from src.logic.container_mgr import (
    container_exists,
    container_is_running,
    exec_command,
    remove_container,
    get_container_status,
)


def init_sandbox(
    name: str,
    image: str,
    overlay_dir: str,
    project_dir: str,
) -> subprocess.CompletedProcess:
    """Initialize (or reinitialize) the sandbox container.

    Removes the existing container (if any) and creates a fresh one
    with the overlay directory mounted at the real source path.

    Args:
        name: Container name.
        image: Container image to use.
        overlay_dir: Path to the overlay directory (tmpfs copy of source).
        project_dir: The real source path where the overlay is mounted.

    Returns:
        CompletedProcess from the initial command.
    """
    from src.logic.container_mgr import create_container

    if container_exists(name):
        remove_container(name)
    create_container(name, image, overlay_dir, project_dir)
    subprocess.run(
        ["podman", "start", name],
        capture_output=True,
        text=True,
        check=True,
    )
    return exec_command(name, "ls")


def run_command(
    name: str,
    command: str,
    image: str,
    auto_discard: bool = False,
) -> subprocess.CompletedProcess:
    """Run a command in the sandbox container.

    Runs the given command inside the container. The container must have
    been initialized first (via --init). Optionally removes the container
    after execution.

    Args:
        name: Container name.
        command: Shell command to execute.
        image: Container image to use.
        auto_discard: If True, remove the container after the command.

    Returns:
        CompletedProcess with the command's stdout/stderr.

    Raises:
        RuntimeError: If the container does not exist or is not running.
    """
    if not container_exists(name):
        raise RuntimeError(
            f"Container {name} does not exist. Run --init first."
        )
    if not container_is_running(name):
        raise RuntimeError(
            f"Container {name} exists but is not running. Run --init first."
        )
    result = exec_command(name, command)
    if auto_discard:
        remove_container(name)
    return result


def remove(name: str) -> subprocess.CompletedProcess:
    """Remove the sandbox container.

    Args:
        name: Container name.

    Returns:
        CompletedProcess from the podman rm call.
    """
    return remove_container(name)


def status(name: str) -> dict:
    """Get the status of the sandbox container.

    Args:
        name: Container name.

    Returns:
        Dict with keys: exists, running, status.
    """
    return get_container_status(name)
