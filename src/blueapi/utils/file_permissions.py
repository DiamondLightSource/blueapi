import os
import stat
from pathlib import Path


def is_sgid_enabled(path: Path) -> bool:
    """Check if the SGID bit is enabled so that new files created
    under a directory owned by a group are owned by that same group.

    See https://www.redhat.com/en/blog/suid-sgid-sticky-bit

    Args:
        path: Path to the file to check

    Returns:
        bool: True if the SGID bit is enabled
    """

    mask = os.stat(path).st_mode
    return bool(mask & stat.S_ISGID)
