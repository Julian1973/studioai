#!/usr/bin/env python3
"""T43 — the compatibility links must be real links.

The Projects restructure (RESTRUCTURE_SPEC_PROJECTS.md) moved every Crystal Bears file into
projects/crystal-bears/ and left symbolic links at the old paths (shows/, cb-output/,
engine/config, cb-studio/data/scripts, the root show documents) for one release, because
older data files still name those paths. On a Windows checkout without symlink support
(`git config core.symlinks false`, the default without Developer Mode) git writes each link
as a tiny TEXT FILE containing the target path — and the studio would then read a 40-byte
file where it expects a directory. That failure is confusing; this check makes it loud.

    python3 tools/check_links.py        # exit 0 = every link resolves; exit 1 = names the broken ones

serve.py runs it at start-up and refuses to serve on a broken link, printing the fix.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# (link path, expected target as written into the link)
COMPATIBILITY_LINKS = [
    ("shows", "projects"),
    ("cb-output", "projects/crystal-bears/episodes/output"),
    ("engine/config", "../projects/crystal-bears/canon"),
    ("cb-studio/data/scripts", "../../projects/crystal-bears/episodes/scripts"),
    ("CRYSTAL_BEARS_LOCKED_CANON.md", "projects/crystal-bears/canon/LOCKED_CANON.md"),
    ("CRYSTAL_BEARS_STUDIO_BIBLE.md", "projects/crystal-bears/SHOW_BIBLE.md"),
    ("EP1_GATE1_STORYBOARD.md", "projects/crystal-bears/docs/EP1_GATE1_STORYBOARD.md"),
]

FIX = ("Fix: on Windows enable Developer Mode (Settings > For developers), then run\n"
       "  git config core.symlinks true\n  git checkout -- .\n"
       "in the studio folder, or re-clone the repository. On macOS/Linux, re-run\n"
       "  git checkout -- <path>\nfor each path listed.")


def broken_links(root: pathlib.Path = ROOT) -> list[str]:
    problems = []
    for rel, target in COMPATIBILITY_LINKS:
        p = root / rel
        if not p.is_symlink():
            if p.exists():
                # A real file/dir where a link should be: on Windows-without-symlinks this is
                # git's text placeholder; on any OS it could be a stale copy that will drift.
                kind = "directory" if p.is_dir() else f"{p.stat().st_size}-byte file"
                problems.append(f"{rel}: is a real {kind}, not a link → {target}")
            else:
                problems.append(f"{rel}: missing (expected link → {target})")
            continue
        if not p.exists():
            problems.append(f"{rel}: link is broken (points to {p.readlink()}, which does not exist)")
    return problems


def main() -> int:
    problems = broken_links()
    if not problems:
        print(f"compatibility links OK ({len(COMPATIBILITY_LINKS)} checked)")
        return 0
    print("COMPATIBILITY LINKS BROKEN — the studio cannot run safely from this checkout:")
    for line in problems:
        print("  " + line)
    print(FIX)
    return 1


if __name__ == "__main__":
    sys.exit(main())
