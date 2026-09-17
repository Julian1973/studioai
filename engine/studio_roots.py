"""Trusted source/data roots for split Studio deployments."""
from __future__ import annotations

import os
from pathlib import Path


def source_root(default: str | Path) -> Path:
    return Path(os.environ.get("STUDIO_SOURCE_ROOT") or default).expanduser().resolve()


def data_root(default: str | Path) -> Path:
    configured = os.environ.get("STUDIO_DATA_ROOT")
    root = Path(configured or source_root(default)).expanduser().resolve()
    if configured and not root.is_dir():
        raise ValueError(f"STUDIO_DATA_ROOT does not exist or is not a directory: {root}")
    return root


def trusted_roots(default: str | Path) -> tuple[Path, ...]:
    roots = (source_root(default), data_root(default))
    return tuple(dict.fromkeys(roots))


def trusted_path(path: str | Path, default: str | Path) -> Path:
    """Resolve *path* only when its final target is under a configured root."""
    resolved = Path(path).expanduser().resolve()
    for root in trusted_roots(default):
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    raise ValueError(f"path escapes configured Studio roots: {path}")


def is_trusted(path: str | Path, default: str | Path) -> bool:
    try:
        trusted_path(path, default)
        return True
    except (OSError, ValueError):
        return False


def relative_trusted(path: str | Path, default: str | Path) -> str:
    resolved = trusted_path(path, default)
    for root in trusted_roots(default):
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            continue
    raise ValueError(f"path is not under a configured Studio root: {path}")
