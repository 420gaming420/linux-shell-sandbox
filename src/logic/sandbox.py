"""
Sandbox module - ephemeral copy-on-write overlay for command execution.

Uses /tmp (which is tmpfs on this system) as the backing store for an
ephemeral copy of the project directory. All writes happen in-memory and
are discarded when the sandbox exits.
"""

import subprocess
from src.logic.overlay import cleanup, create_overlay
from src.logic.shell_runner import run_commands

__all__ = ['create_overlay', 'cleanup', 'run_commands']


def run_sandbox(
    project_dir: str,
    commands: str | None = None,
    interactive: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess:
    """Full sandbox lifecycle: create overlay, run commands, cleanup.

    Args:
        project_dir: Absolute path to the project directory.
        commands: Optional string of commands to execute.
        interactive: Run an interactive shell if no commands provided.
        timeout: Timeout in seconds for non-interactive mode.

    Returns:
        CompletedProcess with the shell output.
    """
    overlay = create_overlay(project_dir)
    try:
        result = run_commands(overlay, commands, interactive, timeout)
    finally:
        cleanup(overlay)
    return result
