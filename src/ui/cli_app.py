"""
CLI application - interactive sandbox shell.

Spawns an ephemeral copy of the project on tmpfs and gives the user
an interactive bash prompt. All commands run inside the overlay.
When the user types 'exit' or the shell ends, the overlay is deleted.
"""

import os
import sys
from src.logic.sandbox import create_overlay, run_commands, cleanup


def get_project_dir() -> str:
    """Determine the project directory (project/ subfolder).

    Returns:
        Absolute path to the project directory.
    """
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'project',
    )


class CliApp:
    """Interactive sandbox shell application."""

    def __init__(self, project_dir: str) -> None:
        self.project_dir = os.path.abspath(project_dir)
        self.overlay_dir: str = ''
        self._proc = None

    def _create_banner(self) -> None:
        """Print a banner showing the sandbox is active."""
        print(f'=== Sandbox Active ===')
        print(f'Project: {self.project_dir}')
        print(f'Overlay: {self.overlay_dir}')
        print(f'Type "exit" or press Ctrl+D to leave the sandbox.')
        print(f'======================')

    def _cleanup(self) -> None:
        """Clean up the overlay and any running process."""
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except Exception:
                self._proc.kill()
        if self.overlay_dir:
            cleanup(self.overlay_dir)

    def run(self) -> int:
        """Run the interactive sandbox shell.

        Returns:
            Exit code (0 = success).
        """
        overlay = create_overlay(self.project_dir)
        self.overlay_dir = overlay

        try:
            self._create_banner()
            result = run_commands(
                overlay,
                commands=None,
                interactive=True,
                timeout=None,
            )
            return result.returncode or 0
        except KeyboardInterrupt:
            print()
            return 130
        except Exception as e:
            print(f'Error: {e}', file=sys.stderr)
            return 1
        finally:
            self._cleanup()
            print()
            print('=== Sandbox exited. Overlay discarded. ===')


def main() -> int:
    """Entry point for the CLI application."""
    project_dir = get_project_dir()
    if not os.path.isdir(project_dir):
        print(f"Error: SANDBOX_PROJECT_DIR does not exist: {project_dir}", file=sys.stderr)
        return 1
    app = CliApp(project_dir)
    return app.run()


if __name__ == '__main__':
    sys.exit(main())
