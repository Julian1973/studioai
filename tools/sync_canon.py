#!/usr/bin/env python3
"""ONE CANON per project (Restructure Phase 1 / T28, Phase 3 repointed, T54 per project). The single
source of truth is the project's canon/LOCKED_CANON.md — paths.CANON (root CRYSTAL_BEARS_LOCKED_CANON.md
is a compat symlink to it for the first project). The project's lock_policy.json declares the
compatibility copies that are GENERATED from the sources by this script and hash-verified; the old
stamped skills/*/references/ copies were retired in T52 (the chairs are generic now — a project's canon
is read from its own canon/, never copied beside a chair). Editing a copy is drift; this script shouts
and fixes.

    python3 tools/sync_canon.py                          # regenerate copies for the active project
    python3 tools/sync_canon.py --check                  # verify only — exit 1 on any drift
    python3 tools/sync_canon.py --project box-monsters   # another project (its profile picks the paths)
"""
import sys, os, glob, hashlib, json, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))


def _project_arg(argv):
    for i, a in enumerate(argv):
        if a == "--project" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--project="):
            return a.split("=", 1)[1]
    return None


_pid = _project_arg(sys.argv)
if _pid:
    os.environ["STUDIO_PROJECT"] = _pid
import paths as P  # noqa: E402 — the project profile is the only path authority (T44)
SRC = P.CANON
POLICY = P.LOCK_POLICY
STAMP = ("<!-- AUTO-GENERATED COPY — DO NOT EDIT. The single source of truth is "
         f"/{P.rel(P.CANON)}. Regenerate: python3 tools/sync_canon.py -->\n\n")

def body(path):
    t = open(path, encoding="utf-8").read()
    return t.split("-->\n\n", 1)[1] if t.startswith("<!-- AUTO-GENERATED") and "-->\n\n" in t else t

def main():
    check = "--check" in sys.argv
    if not SRC or not os.path.exists(SRC):
        print(f"canon: {P.PROJECT_ID} has no locked canon yet ({P.rel(SRC) if SRC else 'undeclared'}) — nothing to sync")
        return
    src = open(SRC, encoding="utf-8").read()
    h = hashlib.sha256(src.encode()).hexdigest()[:12]
    policy = json.load(open(POLICY, encoding="utf-8")) if POLICY and os.path.exists(POLICY) else {}
    # Stamped chair-side copies (policy.skillCanonCopiesGlob) are only maintained where a references/
    # directory still exists — T52 retired them; a glob that matches nothing is simply empty.
    pattern = policy.get("skillCanonCopiesGlob") or ""
    copies = sorted(c for c in glob.glob(os.path.join(ROOT, pattern)) if os.path.isdir(os.path.dirname(c))) if pattern else []
    drift = []
    for c in copies:
        if not os.path.exists(c) or hashlib.sha256(body(c).encode()).hexdigest()[:12] != h:
            drift.append(c)
            if not check:
                os.makedirs(os.path.dirname(c), exist_ok=True)
                open(c, "w", encoding="utf-8").write(STAMP + src)

    # Runtime and legacy paths are compatibility mirrors, never independent canon.
    raw_copies = []
    for item in policy.get("compatibilityCopies", []):
        source_rel = policy["sources"][item["source"]]
        source = os.path.join(ROOT, source_rel)
        target = os.path.join(ROOT, item["path"])
        raw_copies.append(target)
        matches = (os.path.exists(target) and
                   hashlib.sha256(open(source, "rb").read()).digest() ==
                   hashlib.sha256(open(target, "rb").read()).digest())
        if not matches:
            drift.append(target)
            if not check:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(source, target)
    if check:
        if drift:
            print("CANON DRIFT (BLOCK):"); [print("  " + d) for d in drift]; sys.exit(1)
        print(f"canon in sync — {len(copies)} stamped and {len(raw_copies)} raw copies match source {h}"); return
    print(f"canon source {h} -> {len(copies)} stamped + {len(raw_copies)} raw copies " + ("regenerated: " + str(len(drift)) if drift else "(all already in sync)"))

if __name__ == "__main__":
    main()
