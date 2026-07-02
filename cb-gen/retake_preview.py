#!/usr/bin/env python3
"""DIRECTOR CHECK — preview only. Reads {pkg, scene, locator, issue, change, episode} as JSON on stdin, resolves the
shot the locator points at (a canonical Ref like 1.B4#shot7 OR a review timecode like 0:50), and prints how the show's
Director rewrites the plain-English note into precise, continuity-locked retake wording. NO render, no splice. The
LAST stdout line is the JSON result ({ok, ref, shot_action, brief}). Run from cb-gen (so media/ + ../cb-output resolve).
"""
import sys, json, os

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
