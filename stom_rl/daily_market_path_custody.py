"""Windows reparse-boundary checks for daily-market evidence custody."""

from __future__ import annotations

import stat
from pathlib import Path


def has_reparse_component(path: Path) -> bool:
    """Return true when an existing path component is a symlink or junction."""
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    for component in (path, *path.parents):
        try:
            attributes = int(getattr(component.lstat(), "st_file_attributes", 0))
        except OSError:
            continue
        if attributes & reparse_flag:
            return True
    return False


__all__ = ["has_reparse_component"]
