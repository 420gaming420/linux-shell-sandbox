"""
Container manager - low-level podman CLI helpers.

Provides functions to create, exec into, check status of, and remove
podman containers. Each function wraps a podman CLI call and returns
structured results.
"""

import subprocess
from typing import Optional


def _run_podman(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a podman command and return the result.

    Args:
        args: List of podman arguments (without 'podman' prefix).
        check: If True, raise on non-zero exit code.

    Returns:
        CompletedProcess instance.
    """
    cmd = ["podman"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check,
    )


def container_exists(name: str) -> bool:
    """Check if a container with the given name exists.

    Args:
        name: Container name.

    Returns:
        True if the container exists (any state).
    """
    result = subprocess.run(
        ["podman", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    return name in result.stdout.strip().splitlines()


def container_is_running(name: str) -> bool:
    """Check if a container is currently running.

    Args:
        name: Container name.

    Returns:
        True if the container is running.
    """
    result = subprocess.run(
        ["podman", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    return name in result.stdout.strip().splitlines()


def create_container(
    name: str,
    image: str,
    overlay_dir: str,
    project_dir: str,
) -> subprocess.CompletedProcess:
    """Create a new sandbox container.

    Creates a container with:
    - Overlay directory (tmpfs copy of source) bind-mounted at the real
      source path (e.g., /path/to/project) so the container never sees
      the live source.
    - sleep infinity as the main process

    Args:
        name: Container name.
        image: Container image to use.
        overlay_dir: Path to the overlay directory (tmpfs copy of source).
        project_dir: The real source path to mount the overlay at.

    Returns:
        CompletedProcess from the podman create call.
    """
    return _run_podman([
        "create",
        "--name", name,
        "-v", f"{overlay_dir}:{project_dir}:rw",
        "-w", project_dir,
        image,
        "sleep", "infinity",
    ])


def exec_command(
    name: str,
    command: str,
) -> subprocess.CompletedProcess:
    """Execute a shell command inside the container.

    Runs: bash -c "$command"
    The shell is non-interactive (-i) so it works with piped input.
    The container's working directory is set to the project path via --workdir.

    Args:
        name: Container name.
        command: Shell command to execute.

    Returns:
        CompletedProcess with stdout/stderr from the command.
    """
    return _run_podman(
        [
            "exec", name, "bash", "-c", command,
        ],
        check=False,
    )


def remove_container(name: str) -> subprocess.CompletedProcess:
    """Remove a container, forcing if it is running.

    Args:
        name: Container name.

    Returns:
        CompletedProcess from the podman rm call.
    """
    return _run_podman(["rm", "-f", name])


def get_container_status(name: str) -> dict:
    """Get the status of a container.

    Args:
        name: Container name.

    Returns:
        Dict with keys: exists, running, status_string.
    """
    exists = container_exists(name)
    running = container_is_running(name) if exists else False

    status_string = "not found"
    if exists:
        result = _run_podman([
            "ps", "-a", "--filter", f"name=^{name}$",
            "--format", "{{.Status}}",
        ], check=False)
        status_string = result.stdout.strip() if result.stdout.strip() else "unknown"

    mem_usage = ""
    if exists and running:
        result = _run_podman(
            ["stats", "--no-stream", name],
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Output has a header line + one data line.
            # Header:  ID  NAME  CPU%  MEM USAGE / LIMIT  MEM%  ...
            # Data:    <id>  <name>  <cpu%>  <mem> / <limit>  <mem%>  ...
            lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
            if len(lines) >= 2:
                # Last line is the data
                data = lines[-1]
                # Split by whitespace, but "MEM / LIMIT" has spaces
                # Format: ID NAME CPU% MEM / LIMIT MEM% NET_IO BLOCK_IO PIDS ...
                # We need: mem and limit which are fields 4 and 5
                # But "102.4kB / 33.56GB" splits into 3 tokens
                # So data fields: [0]=ID, [1]=NAME, [2]=CPU%, [3]=MEM, [4]=/, [5]=LIMIT, [6]=MEM%
                parts = data.split()
                if len(parts) >= 6:
                    mem_usage = f"{parts[3]} / {parts[5]}"

    return {
        "exists": exists,
        "running": running,
        "status": status_string,
        "memory": mem_usage,
    }
