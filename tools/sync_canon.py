#!/usr/bin/env python3
"""ONE CANON (Restructure Phase 1 / T28, Phase 3 repointed). The single source of truth is
shows/crystal-bears/canon/LOCKED_CANON.md (root CRYSTAL_BEARS_LOCKED_CANON.md is now a compat
symlink to it). Every skills/*/references/ copy is GENERATED from it by this script, stamped,
and hash-verified. Editing a copy is drift; this script shouts and fixes.

    python3 tools/sync_canon.py            # regenerate all copies from the source
    python3 tools/sync_canon.py --check    # verify only — exit 1 on any drift (CI / Continuity)
"""
import sys, os, glob, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "shows", "crystal-bears", "canon", "LOCKED_CANON.md")
STAMP = ("<!-- AUTO-GENERATED COPY — DO NOT EDIT. The single source of truth is "
         "/shows/crystal-bears/canon/LOCKED_CANON.md. Regenerate: python3 tools/sync_canon.py -->\n\n")

def body(path):
    t = open(path, encoding="utf-8").read()
    return t.split("-->\n\n", 1)[1] if t.startswith("<!-- AUTO-GENERATED") and "-->\n\n" in t else t

def main():
    check = "--check" in sys.argv
    src = open(SRC, encoding="utf-8").read()
    h = hashlib.sha256(src.encode()).hexdigest()[:12]
    # every crystal-bears-* skill gets a copy, whether or not references/ + the file exist yet
    skill_dirs = sorted(d for d in glob.glob(os.path.join(ROOT, "skills", "crystal-bears-*")) if os.path.isdir(d))
    copies = [os.path.join(d, "references", "CRYSTAL_BEARS_LOCKED_CANON.md") for d in skill_dirs]
    drift = []
    for c in copies:
        if not os.path.exists(c) or hashlib.sha256(body(c).encode()).hexdigest()[:12] != h:
            drift.append(c)
            if not check:
                os.makedirs(os.path.dirname(c), exist_ok=True)
                open(c, "w", encoding="utf-8").write(STAMP + src)
    if check:
        if drift:
            print("CANON DRIFT (BLOCK):"); [print("  " + d) for d in drift]; sys.exit(1)
        print(f"canon in sync — {len(copies)} copies match source {h}"); return
    print(f"canon source {h} -> {len(copies)} copies " + ("regenerated: " + str(len(drift)) if drift else "(all already in sync)"))

if __name__ == "__main__":
    main()
