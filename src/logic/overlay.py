"""
Overlay creation and cleanup for the sandbox.

Uses fuse-overlayfs to create a true copy-on-write overlay of the project
directory. The lower layer points to the original project (on the real
filesystem, read-only), and the upper layer is a small tmpfs directory
that only stores modified/created files. This avoids copying the entire
project into tmpfs for each sandbox.
"""

import os
import shutil
import subprocess
import tempfile


def create_overlay(project_dir: str) -> str:
    """Create a fuse-overlayfs overlay of the project.

    Creates a copy-on-write overlay where:
    - lowerdir = original project directory (on real FS, read-only view)
    - upperdir = small tmpfs directory for deltas (modified/created files)
    - workdir = tmpfs directory for overlay operations
    - merged = mount point returned to the caller

    Args:
        project_dir: Absolute path to the project directory to sandbox.

    Returns:
        Absolute path to the overlay mount point.

    Raises:
        RuntimeError: If fuse-overlayfs is not available or mount fails.
    """
    overlay_base = tempfile.mkdtemp(prefix='sandbox_', dir='/tmp')
    upper_dir = os.path.join(overlay_base, 'upper')
    work_dir = os.path.join(overlay_base, 'work')
    merged_dir = os.path.join(overlay_base, 'merged')

    os.makedirs(upper_dir)
    os.makedirs(work_dir)
    os.makedirs(merged_dir)

    # Mount the fuse-overlayfs with the project as the lower (read-only) layer.
    # Only modified/created files are stored in upper/ on tmpfs.
    result = subprocess.run(
        [
            "fuse-overlayfs",
            "-o", f"lowerdir={project_dir},upperdir={upper_dir},workdir={work_dir}",
            merged_dir,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        shutil.rmtree(overlay_base)
        raise RuntimeError(
            f"Failed to mount fuse-overlayfs: {result.stderr.strip()}"
        )

    return merged_dir


def cleanup(overlay_dir: str) -> None:
    """Unmount the overlay and remove all temporary directories.

    Args:
        overlay_dir: Path to the overlay mount point (merged dir).
    """
    try:
        subprocess.run(["umount", overlay_dir], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        # Try lazy unmount if normal unmount fails (e.g., mount is busy)
        subprocess.run(["umount", "-l", overlay_dir], capture_output=True, text=True)

    # Remove the base temp directory (includes lower, upper, work, merged)
    base_dir = os.path.dirname(overlay_dir)
    shutil.rmtree(base_dir, ignore_errors=True)
