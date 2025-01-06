import stat
from pathlib import Path


def is_sgid_set(path: Path) -> bool:
    """Check if the SGID bit is set so that new files created
    under a directory owned by a group are owned by that same group.

    See https://www.redhat.com/en/blog/suid-sgid-sticky-bit

    Args:
        path: Path to the file to check

    Returns:
        bool: True if the SGID bit is set
    """

    mask = path.stat().st_mode
    return bool(mask & stat.S_ISGID)


def get_owner_gid(path: Path) -> int:
    """Get the GID of the owner of a file

    Args:
        path: Path to the file to check

    Returns:
        bool: The GID of the file owner
    """

    return path.stat().st_gid
