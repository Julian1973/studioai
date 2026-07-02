#!/usr/bin/env python3
"""Safety test for serve.py static-file hardening (root-based allow-list).

Run it AFTER restarting the studio server (the hardening only loads on restart):
    python3 cb-studio/serve.py                   # terminal 1
    python3 cb-studio/test_static_hardening.py   # terminal 2

Policy under test: BLOCKED by default — a file is served ONLY if it sits under an approved root
with an approved extension, or is an explicitly-approved exact file. This test proves:
  • secrets / source / backups / logs / state / node_modules / audit dirs / dotfiles  → 404
  • a RANDOM .json / .md / .txt OUTSIDE an approved root                                → 404
  • the real assets the SPA fetches                                                     → 200
Exit code 0 = all pass. Pass a base URL as arg 1 to override (default http://localhost:8765).
"""
import sys, urllib.request, urllib.error

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8765"

# 1) Sensitive paths — must be REFUSED (404/403).
BLOCKED_SENSITIVE = [
    "/cb-gen/.env", "/.env", "/cb-gen/cb_prompts.py", "/cb-gen/cb_gen.py", "/cb-studio/serve.py",
    "/cb-gen/locked.json", "/cb-gen/notes.json", "/cb-studio/data/projects-index.json",
    "/.replit", "/.DS_Store", "/node_modules/", "/_audit_unpack/", "/client/index.html",
    "/cb-gen/_master3.log", "/server.js.bak", "/../cb-gen/.env",
]

# 2) THE POINT OF THIS REVISION — random JSON / MD / TXT OUTSIDE an approved root must be REFUSED (404),
#    even when the extension itself is otherwise legitimate elsewhere.
BLOCKED_OUTSIDE_ROOTS = [
    "/cb-gen/continuity.json",          # JSON in a non-approved folder
    "/cb-gen/config/continuity.json",   # JSON in config — only characters.json is approved there
    "/cb-gen/config/locations.json",    # ditto
    "/cb-output/Ep1_theme.json",        # JSON in cb-output but NOT a *_beat_package.json
    "/STUDIO_COMEDY_DOCTRINE.md",       # a doc that is not the show-bible
    "/README.md",                       # any other markdown doc
    "/CRYSTAL_BEARS_PIPELINE.md",       # ditto
    "/random-not-real.txt",             # stray text at root
    "/cb-studio/data/anything.md",      # MD inside the approved data root (wrong extension there)
    "/secrets.json",                    # stray JSON at root
]

# 3) Real assets the SPA fetches — must be SERVED (200). All of these exist on disk.
ALLOWED = [
    "/cb-studio/app.html",
    "/cb-gen/config/characters.json",
    "/CRYSTAL_BEARS_LOCKED_CANON.md",
    "/cb-studio/data/episodes.json",
    "/cb-studio/data/media-index.json",
    "/cb-studio/data/scripts/Ep1_The_Adventure_Begins.txt",
    "/cb-seed/assets/final_turnarounds/CB_Fuzzby.jpeg",
    "/cb-gen/media/AB_1.B1_flux.png",
]


def status(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=6) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return f"ERR({e})"


def main():
    bad = 0
    print(f"== static-file hardening test  →  {BASE} ==")
    for title, paths, want_block in (
        ("BLOCKED — sensitive (expect 404/403)", BLOCKED_SENSITIVE, True),
        ("BLOCKED — random json/md/txt outside approved roots (expect 404/403)", BLOCKED_OUTSIDE_ROOTS, True),
        ("ALLOWED — real SPA assets (expect 200)", ALLOWED, False),
    ):
        print(f"\n{title}:")
        for p in paths:
            s = status(p)
            ok = (s in (404, 403)) if want_block else (s == 200)
            bad += (not ok)
            print(f"  {'PASS' if ok else 'FAIL'}  [{s}]  {p}")
    print("\n" + ("ALL PASS ✓" if not bad else f"{bad} FAILURE(S) ✗"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
