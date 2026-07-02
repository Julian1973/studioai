#!/usr/bin/env python3
"""cb_golden.py — T10, the golden-set harness.

Stores a known-good snapshot of BOTH prompt paths and diffs current output against it:
  • the Seedance clip-prompt baseline (cb_segprompt.for_beat) on Ep1 1.B1-1.B3 — the same 3 beats
    CLAUDE.md's "Baseline proof" already names.
  • the keyframe prompt (cb_scene.keyframe_for) on all 4 Ep1 Scene-1 beats (1.B1-1.B4) — anchor + 3
    chained beats, so a chain-vs-anchor formatting regression shows up too.

CLAUDE.md hard rule: no prompt-touching commit merges without this diff shown. A diff is not automatically
wrong — a ticket can deliberately change a prompt — but it must be SHOWN to Julian before the golden is
recaptured, never silently overwritten.

    python3 cb_golden.py diff       # compare current output vs the stored golden set (exit 1 on any diff)
    python3 cb_golden.py capture    # OVERWRITE the golden set with current output (only after Julian has seen the diff)
"""
import os, sys, json, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(HERE, "goldens")
PKG = os.path.join(HERE, "..", "cb-output", "Ep1_Episode_1_beat_package.json")
SEGPROMPT_BEATS = ["1.B1", "1.B2", "1.B3"]
KEYFRAME_BEATS = ["1.B1", "1.B2", "1.B3", "1.B4"]


def _pkg():
    return json.load(open(PKG))


def current_snapshot():
    """{key: prompt text} for every golden-set entry, built the SAME way the live paths build them (cb_beats.run's
    scene lookup for segprompt; cb_scene.keyframe_for for the keyframe) — never a bespoke re-implementation."""
    import cb_segprompt, cb_scene
    d = _pkg()
    beats = d["beats"]
    by_code = {(b.get("beatCode") or b.get("shotCode")): b for b in beats}
    scenes = {str(s.get("sceneNumber")): s for s in (d.get("scenes") or [])}
    out = {}
    for code in SEGPROMPT_BEATS:
        b = by_code.get(code)
        if not b:
            continue
        sc = scenes.get(str(b.get("sceneNumber")))
        out[f"segprompt__{code}"] = cb_segprompt.for_beat(b, sc) or ""
    for code in KEYFRAME_BEATS:
        if code not in by_code:
            continue
        prompt, _refs, _info = cb_scene.keyframe_for(beats, code, "Ep1")
        out[f"keyframe__{code}"] = prompt
    return out


def _golden_path(key):
    return os.path.join(GOLDEN_DIR, key + ".txt")


def diff():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    snap = current_snapshot()
    any_diff = False
    for key, text in snap.items():
        gp = _golden_path(key)
        if not os.path.exists(gp):
            print(f"[{key}] NO GOLDEN STORED YET — run 'python3 cb_golden.py capture' once Julian has reviewed this output.")
            any_diff = True
            continue
        golden = open(gp, encoding="utf-8").read()
        if golden == text:
            print(f"[{key}] OK — identical to golden")
        else:
            any_diff = True
            print(f"[{key}] DIFF —")
            for line in difflib.unified_diff(golden.splitlines(), text.splitlines(),
                                              fromfile="golden", tofile="current", lineterm=""):
                print("  " + line)
    print()
    print("ZERO DIFFS — safe to merge" if not any_diff
          else "DIFFS FOUND — show Julian before merging (CLAUDE.md hard rule); recapture only after he has seen this")
    return 1 if any_diff else 0


def capture():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    snap = current_snapshot()
    for key, text in snap.items():
        open(_golden_path(key), "w", encoding="utf-8").write(text)
        print(f"captured [{key}] ({len(text)} chars)")


if __name__ == "__main__":
    os.chdir(HERE)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "diff"
    if cmd == "capture":
        capture()
    else:
        sys.exit(diff())
