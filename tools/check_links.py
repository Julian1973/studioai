#!/usr/bin/env python3
"""T43 — the compatibility links must be real links.

The Projects restructure (RESTRUCTURE_SPEC_PROJECTS.md) moved every Crystal Bears file into
projects/crystal-bears/ and left symbolic links at the old paths (shows/, cb-output/,
engine/config, cb-studio/data/scripts, the root show documents) for one release, because
older data files still name those paths. On a Windows checkout without symlink support
(`git config core.symlinks false`, the default without Developer Mode) git writes each link
as a tiny TEXT FILE containing the target path — and the studio would then read a 40-byte
file where it expects a directory. That failure is confusing; this check makes it loud.

    python3 tools/check_links.py            # exit 0 = every link resolves; exit 1 = names the broken ones
    python3 tools/check_links.py --migrate  # an old checkout: clear untracked files from engine/config first

serve.py runs it at start-up and refuses to serve on a broken link, printing the fix.
"""
from __future__ import annotations

import os
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
    # T44: the project's assets root. The REAL directory stays at cb-seed/assets for one release —
    # identity digests (cb_identity) hash the resolved absolute path, so moving the bytes would mark
    # every approved direction stale on a working machine. The project owns the path; the link
    # points at the bytes. T61 decides the migration (content digests, or a one-time relock).
    ("projects/crystal-bears/assets", "../../cb-seed/assets"),
    # T52: the chairs are generic (studio/chairs/<role>) and the show's own chair documents live in
    # projects/crystal-bears/chairs/. The project's lock_policy.json still hashes the runtime sources
    # at the old skills/ paths; these links keep those hashes (and every approved package's canon
    # profile digest) current until Julian re-locks canon at T61.
    ("skills/crystal-bears-writer/SKILL.md", "../../projects/crystal-bears/chairs/writer.md"),
    ("skills/crystal-bears-director/SKILL.md", "../../projects/crystal-bears/chairs/director.md"),
    ("skills/crystal-bears-cinematographer/SKILL.md", "../../projects/crystal-bears/chairs/cinematographer.md"),
    ("skills/crystal-bears-voice-director/SKILL.md", "../../projects/crystal-bears/chairs/voice-director.md"),
    ("skills/crystal-bears-composer/SKILL.md", "../../projects/crystal-bears/chairs/composer.md"),
    ("skills/crystal-bears-continuity/SKILL.md", "../../projects/crystal-bears/chairs/continuity.md"),
    ("skills/crystal-bears-post/SKILL.md", "../../projects/crystal-bears/chairs/post.md"),
    ("skills/seedance-production-director/SKILL.md", "../../studio/chairs/animation/SKILL.md"),
]

# Real directories that a checkout made BEFORE the restructure may still carry at the old path —
# `--migrate` moves their contents into the project and replaces them with the link.
MIGRATABLE = {
    # A pre-T43 checkout may hold untracked per-machine files here (backup.json) that stop git from
    # replacing the directory with the link; migrate first, then `git checkout`.
    "engine/config": "projects/crystal-bears/canon",
}

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


def migrate(root: pathlib.Path = ROOT) -> list[str]:
    """Move a pre-restructure real directory into the project and leave the link behind.
    Idempotent; never deletes — a name collision inside the project is reported, not overwritten."""
    import shutil
    done = []
    for rel, target in MIGRATABLE.items():
        old = root / rel
        new = root / target
        if old.is_symlink() or not old.exists():
            continue
        new.mkdir(parents=True, exist_ok=True)
        for item in sorted(old.iterdir()):
            dest = new / item.name
            if dest.exists():
                done.append(f"SKIPPED {rel}/{item.name}: already exists in {target}")
                continue
            shutil.move(str(item), str(dest))
            done.append(f"moved {rel}/{item.name} → {target}/{item.name}")
        try:
            old.rmdir()
        except OSError:
            done.append(f"LEFT {rel}: not empty after migration — check the SKIPPED items")
            continue
        link_target = dict(COMPATIBILITY_LINKS)[rel]
        os.symlink(link_target, old, target_is_directory=True)
        done.append(f"linked {rel} → {link_target}")
    return done


def main() -> int:
    if "--migrate" in sys.argv:
        for line in migrate():
            print("  " + line)
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
