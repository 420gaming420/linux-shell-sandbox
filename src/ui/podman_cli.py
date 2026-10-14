"""
Podman CLI application - container-based sandbox shell.

Provides a command-line interface for running shell commands inside
a podman container with a tmpfs-backed overlay.
"""

import argparse
import os
import sys

from src.logic.config import get_default_image, get_default_project_dir, get_default_sandbox_name
from src.logic.overlay import cleanup as cleanup_overlay
from src.logic.podman_sandbox import init_sandbox, run_command, remove, status
from src.logic.sandbox import create_overlay


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the podman sandbox CLI.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="podman.py",
        description="Run shell commands in a podman container with a tmpfs overlay.",
    )

    parser.add_argument(
        "--sandbox-name", "-n",
        type=str,
        default=get_default_sandbox_name(),
        help=f"Container name (default: {get_default_sandbox_name()}).",
    )
    parser.add_argument(
        "--project-dir", "-d",
        type=str,
        default=get_default_project_dir(),
        help="Project directory to mount (default: ./project/).",
    )
    parser.add_argument(
        "--image", "-i",
        type=str,
        default=get_default_image(),
        help=f"Container image (default: {get_default_image()}).",
    )
    parser.add_argument(
        "--auto-discard", "-a",
        action="store_true",
        default=False,
        help="Remove the container after executing the command.",
    )

    parser.add_argument(
        "--init", "-I",
        action="store_true",
        help="Initialize/recreate the container (clears workspace).",
    )
    parser.add_argument(
        "--status", "-S",
        action="store_true",
        help="Show container status.",
    )
    parser.add_argument(
        "--remove", "-r",
        action="store_true",
        help="Remove the container.",
    )
    parser.add_argument(
        "--mem", "-m",
        action="store_true",
        default=False,
        help="Print container memory usage before and after the command.",
    )

    parser.add_argument(
        "command",
        nargs="?",
        help="Shell command to execute in the sandbox.",
    )

    return parser


class PodmanCliApp:
    """CLI application for the podman sandbox."""

    def __init__(
        self,
        sandbox_name: str,
        project_dir: str,
        image: str,
        auto_discard: bool,
        init: bool,
        show_status: bool,
        remove: bool,
        show_mem: bool,
        command: str | None,
    ) -> None:
        self.sandbox_name = sandbox_name
        self.project_dir = os.path.abspath(project_dir)
        self.image = image
        self.auto_discard = auto_discard
        self.init = init
        self.show_status = show_status
        self.remove = remove
        self.show_mem = show_mem
        self.command = command

    def run(self) -> int:
        """Run the CLI application.

        Returns:
            Exit code (0 = success).
        """
        if not os.path.isdir(self.project_dir):
            print(
                f"Error: SANDBOX_PROJECT_DIR does not exist: {self.project_dir}",
                file=sys.stderr,
            )
            return 1

        # --remove: just remove the container
        if self.remove:
            result = remove(self.sandbox_name)
            if result.returncode != 0:
                print(result.stderr, file=sys.stderr)
                return result.returncode
            return 0

        # --status: show container status
        if self.show_status:
            info = status(self.sandbox_name)
            print(f"Name: {self.sandbox_name}")
            print(f"Exists: {info['exists']}")
            print(f"Running: {info['running']}")
            print(f"Status: {info['status']}")
            if info['memory']:
                print(f"Memory: {info['memory']}")
            return 0

        # --init: create overlay and container
        if self.init:
            overlay_dir = create_overlay(self.project_dir)
            try:
                result = init_sandbox(
                    self.sandbox_name,
                    self.image,
                    overlay_dir,
                    self.project_dir,
                )
                if result.returncode != 0:
                    print(result.stderr, file=sys.stderr)
                    return result.returncode
            except Exception:
                cleanup_overlay(overlay_dir)
                raise

        # No command provided
        if not self.command:
            return 0

        # Run the command
        if self.show_mem:
            info = status(self.sandbox_name)
            if info['exists'] and info['memory']:
                print(f"MEMORY BEFORE: {info['memory']}", file=sys.stderr)
            else:
                print("MEMORY BEFORE: (container not running)", file=sys.stderr)

        result = run_command(
            self.sandbox_name,
            self.command,
            self.image,
            self.auto_discard,
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)

        if self.show_mem:
            info = status(self.sandbox_name)
            if info['exists'] and info['memory']:
                print(f"MEMORY AFTER: {info['memory']}", file=sys.stderr)
            else:
                print("MEMORY AFTER: (container discarded)", file=sys.stderr)

        return result.returncode or 0


def main() -> int:
    """Entry point for the podman CLI application."""
    parser = build_parser()
    args = parser.parse_args()

    app = PodmanCliApp(
        sandbox_name=args.sandbox_name,
        project_dir=args.project_dir,
        image=args.image,
        auto_discard=args.auto_discard,
        init=args.init,
        show_status=args.status,
        remove=args.remove,
        show_mem=args.mem,
        command=args.command,
    )
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
