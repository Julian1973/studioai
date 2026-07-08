#!/usr/bin/env python3
"""tools/backup_media.py — the OFF-MACHINE BACKUP for rendered media (2026-07-08, operational-risk fix).

Confirmed gap: engine/media/ (rendered clips, keyframes, plates, settle/re-mint frames — 453MB as of this
writing) is gitignored by design (generated output, not source) and was found to have ZERO off-machine
backup — a local-disk failure would lose every paid-for render with no recovery path, unlike canon/code
which are safely in git -> GitHub. shows/crystal-bears/canon/ is already git-backed; it's included here too
as a zero-cost belt-and-suspenders copy, not because it needed a new mechanism.

Destination: Julian's own choice (asked directly, 2026-07-08) — the mounted external drive at /Volumes/5t,
not iCloud Drive (my own first pick, correctly stopped before anything synced — an agent choosing an external
cloud destination for proprietary project media without asking is exactly the kind of thing that needs a
human's own call, not mine). Never deletes or moves anything from the source; this is a pure, additive,
repeatable COPY (rsync -a --delete on the backup side only, so the backup mirrors current state without ever
touching engine/media/ itself). Written to fail SAFE if the drive isn't mounted, rather than erroring or
guessing at another location.

Usage:
    python3 tools/backup_media.py           # full sync now
    python3 tools/backup_media.py --dry-run # show what would copy, change nothing

Called automatically (per-beat, not full-sync) by cb_beats.record_approval() the moment a clip is approved —
see that function's own call to backup_one(). This script's __main__ path is for the full catch-up sync and
for a human to re-run manually at any time.
"""
import os, shutil, subprocess, sys, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVE = "/Volumes/5t"
BACKUP_ROOT = os.path.join(DRIVE, "CrystalBears_Backup")

SOURCES = [
    ("engine/media", "media"),
    ("shows/crystal-bears/canon", "canon"),
    # Added 2026-07-08 (workspace-clutter pass): these three are real, irreplaceable Crystal Bears assets
    # (cb-seed/ holds the locked character turnarounds cb_prompts.py references by filename — hand-curated,
    # not regenerable by the pipeline; archive/ and cb_pages/ are historical record) — but at ~790MB combined,
    # too large to put in git without LFS. This backup is the actual off-machine protection for them instead.
    ("cb-seed", "cb-seed"),
    ("archive", "archive"),
    ("cb_pages", "cb_pages"),
]


def _available():
    return os.path.isdir(DRIVE)


def full_sync(dry_run=False):
    if not _available():
        print(f"  BACKUP SKIPPED — {DRIVE} is not mounted right now. "
              "Nothing was copied; the local-only risk still stands until the drive is connected.",
              flush=True)
        return False
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    ok = True
    for src_rel, dst_name in SOURCES:
        src = os.path.join(ROOT, src_rel)
        if not os.path.isdir(src):
            print(f"  (skip — {src_rel} doesn't exist)", flush=True)
            continue
        dst = os.path.join(BACKUP_ROOT, dst_name)
        cmd = ["rsync", "-a", "--delete"] + (["--dry-run", "-v"] if dry_run else []) + [src + "/", dst + "/"]
        print(f"  {'DRY-RUN' if dry_run else 'sync'}: {src_rel} -> {dst}", flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"    FAILED: {r.stderr[:300]}", flush=True)
            ok = False
        elif dry_run:
            lines = [l for l in r.stdout.splitlines() if l and not l.startswith(("sending", "sent ", "total"))]
            print(f"    {len(lines)} file(s) would change", flush=True)
    return ok


def backup_one(path):
    """Copy a single file (a just-approved clip, its sidecars) into the media backup folder. Called from
    cb_beats.record_approval on every approved=True — never blocks or raises on failure (a backup miss is
    logged, not a reason to refuse an approval that already succeeded). No-ops silently if the drive isn't
    mounted at the moment of approval — the full_sync catch-up covers it next time the drive is connected."""
    if not path or not os.path.exists(path) or not _available():
        return False
    try:
        rel = os.path.relpath(path, os.path.join(ROOT, "engine", "media"))
        if rel.startswith(".."):
            return False
        dst = os.path.join(BACKUP_ROOT, "media", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(path, dst)
        return True
    except Exception as e:
        print(f"  (backup_one skipped for {path}: {str(e)[:120]})", flush=True)
        return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Back up engine/media/ + canon to the 5t external drive")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(f"Backup destination: {BACKUP_ROOT}", flush=True)
    ok = full_sync(dry_run=a.dry_run)
    sys.exit(0 if ok else 1)
