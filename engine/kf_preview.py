#!/usr/bin/env python3
"""Print the ACTUAL assembled keyframe prompt for a beat — the exact string build_keyframe_prompt()
sends to the image generator (so the studio card shows what-you-see-is-what-generates).
Usage: python3 kf_preview.py <beat_package.json> <beatCode> [episode]   (run from engine/)"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE); sys.path.insert(0, HERE)
# FIXED 2026-07-12 (full-codebase audit continued): `cb_prompts as P` was imported but never referenced
# anywhere in this file — cb_scene.keyframe_for already imports cb_prompts internally where it's actually
# needed. Dead weight, removed.
import cb_scene

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: kf_preview.py <package> <beatCode> [episode]"})); return
    pkg, beat = sys.argv[1], sys.argv[2]
    episode = sys.argv[3] if len(sys.argv) > 3 else "Ep1"
    try:
        d = json.load(open(os.path.join("..", "cb-output", pkg)))
        beats = d.get("beats") or d.get("shots") or []
        b = next((x for x in beats if str(x.get("beatCode") or x.get("shotCode")) == beat), None)
        if not b:
            print(json.dumps({"error": "beat not found: " + beat})); return
        # FIXED 2026-07-12 (loose-ends pass): was a hand-built dict from cb_scene.keyframe_for's raw return,
        # a near-duplicate of beat_preview.py's own keyframe branch that had already drifted apart once (the
        # lint field) — now cb_scene.keyframe_preview_payload() is the one shared builder both scripts call.
        print(json.dumps(cb_scene.keyframe_preview_payload(beats, beat, episode)))   # card == API (WYSIWYG)
    except Exception as e:
        print(json.dumps({"error": str(e)}))

main()
