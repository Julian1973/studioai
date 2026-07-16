#!/usr/bin/env python3
"""DIRECTOR CHECK — preview only. Reads {pkg, scene, locator, issue, change, episode} as JSON on stdin, resolves the
shot the locator points at (a canonical Ref like 1.B4#shot7 OR a review timecode like 0:50), and prints how the show's
Director rewrites the plain-English note into precise, continuity-locked retake wording. NO render, no splice. The
LAST stdout line is the JSON result ({ok, ref, shot_action, brief}). Run from cb-gen (so media/ + ../cb-output resolve).
"""
import sys, json, os
# FIXED 2026-07-12 (full-codebase audit continued): unlike every sibling preview script (beat_preview.py,
# kf_preview.py, voice_preview.py, sound_brief_preview.py, masters_preview.py), this file had no HERE/chdir/
# sys.path prelude, so its "../cb-output/<pkg>" resolution silently depended on the caller's subprocess cwd
# being correct (today: serve.py's one call site passes cwd=str(ROOT/"engine")) rather than being self-
# sufficient like the rest of its family. A future second caller or a manual debug run from the wrong cwd would
# silently mis-resolve the package path and fail with a generic FileNotFoundError giving no hint that cwd was
# the real cause. Added the same prelude every sibling already uses.
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE); sys.path.insert(0, HERE)

def main():
    try:
        d = json.loads(sys.stdin.read() or "{}")
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"bad input: {e}"})); return
    pkg = d.get("pkg") or ""
    if pkg and "/" not in pkg:                       # basename → the real package path from cb-gen's CWD
        cand = os.path.join("..", "cb-output", pkg)
        pkg = cand if os.path.exists(cand) else pkg
    ep = d.get("episode") or "Ep1"
    scene = d.get("scene")
    try:
        scene = int(scene) if str(scene or "").strip() else None
    except Exception:
        scene = None
    try:
        import cb_retake
        r = cb_retake.preview_brief(pkg, d.get("locator") or "", d.get("issue") or "",
                                    d.get("change") or "", ep, scene)
    except SystemExit as e:
        r = {"ok": False, "error": str(e)[:300]}
    except Exception as e:
        r = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}
    print(json.dumps(r))

if __name__ == "__main__":
    main()
