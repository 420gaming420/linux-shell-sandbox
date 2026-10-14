"""
Command execution inside the sandbox overlay.

Handles both non-interactive (piped commands) and interactive (PTY-based)
shell execution within the overlay directory.
"""

import os
import subprocess
import sys
from typing import Optional


def run_commands(
    overlay_dir: str,
    commands: Optional[str] = None,
    interactive: bool = True,
    timeout: Optional[int] = None,
) -> subprocess.CompletedProcess:
    """Run shell commands inside the sandbox overlay.

    Args:
        overlay_dir: Path to the overlay directory.
        commands: If provided, these commands are piped to the shell.
                  If None, runs an interactive shell.
        interactive: If True and no commands provided, runs an interactive bash shell.
        timeout: Maximum seconds to wait for completion. None for interactive.

    Returns:
        CompletedProcess instance with stdout/stderr captured.
    """
    if commands is not None:
        return _run_non_interactive(overlay_dir, commands, timeout)
    else:
        return _run_interactive(overlay_dir)


def _run_non_interactive(
    overlay_dir: str,
    commands: str,
    timeout: Optional[int],
) -> subprocess.CompletedProcess:
    """Run commands non-interactively as a single bash script.

    Args:
        overlay_dir: Path to the overlay directory.
        commands: Shell commands to execute.
        timeout: Maximum seconds to wait.

    Returns:
        CompletedProcess with captured output.
    """
    full_cmd = f'set -e\n{commands}'
    proc = subprocess.Popen(
        ['bash', '-c', full_cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=overlay_dir,
        text=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
        raise
    return subprocess.CompletedProcess(
        args=['bash', '-c', full_cmd],
        returncode=proc.returncode,
        stdout=out,
    )


def _run_interactive(overlay_dir: str) -> subprocess.CompletedProcess:
    """Run an interactive bash shell using a pseudo-tty.

    Spawns bash -i with PTY for proper terminal behavior (colors,
    job control, etc.). Reads from stdin and writes to stdout in real-time.

    Args:
        overlay_dir: Path to the overlay directory.

    Returns:
        CompletedProcess with the shell exit code.
    """
    import pty
    import select
    import termios
    import tty

    master_in, slave_in = pty.openpty()
    master_out, slave_out = pty.openpty()
    proc = subprocess.Popen(
        ['bash', '-i'],
        stdin=slave_in,
        stdout=slave_out,
        stderr=slave_out,
        cwd=overlay_dir,
    )

    old_attrs = None
    try:
        old_attrs = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
    except Exception:
        pass

    stdin_eof = False
    try:
        while proc.poll() is None:
            rlist, _, _ = select.select(
                [sys.stdin, master_out], [], [], 0.1
            )
            if master_out in rlist:
                try:
                    data = os.read(master_out, 4096)
                    if not data:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                except OSError:
                    break
            if sys.stdin in rlist:
                if stdin_eof:
                    break
                data = os.read(sys.stdin.fileno(), 4096)
                if not data:
                    stdin_eof = True
                else:
                    os.write(master_in, data)
        # Close both master fds to signal EOF to bash
        os.close(master_in)
        os.close(master_out)
        master_in = -1
        master_out = -1
        proc.wait()
    except Exception:
        if master_in >= 0:
            try:
                os.close(master_in)
            except OSError:
                pass
        if master_out >= 0:
            try:
                os.close(master_out)
            except OSError:
                pass
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        raise
    finally:
        if old_attrs is not None:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_attrs)
            except Exception:
                pass

    return subprocess.CompletedProcess(
        args=['bash', '-i'],
        returncode=proc.returncode,
        stdout='',
    )
