#!/usr/bin/env python3
"""Print the ACTUAL assembled prompt for a beat — either the Seedance JSON (the clip take prompt) or the
opening KEYFRAME prompt (the exact string the image generator gets) — so the Cascade studio shows
what-you-see-is-what-generates. Mirrors kf_preview.py.

Usage: python3 beat_preview.py <beat_package.json> <scene> <beatCode> [episode=Ep1] [kind=seedance|keyframe]
       (run from engine/)"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE); sys.path.insert(0, HERE)
import cb_prompts as P, cb_scene, cb_seedance

def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error": "usage: beat_preview.py <package> <scene> <beatCode> [episode] [kind]"})); return
    pkg, scene, beat = sys.argv[1], sys.argv[2], sys.argv[3]
    episode = sys.argv[4] if len(sys.argv) > 4 else "Ep1"
    kind = (sys.argv[5] if len(sys.argv) > 5 else "seedance").lower()
    try:
        d = json.load(open(os.path.join("..", "cb-output", pkg)))
        beats = d.get("beats") or d.get("shots") or []
        b = next((x for x in beats if str(x.get("beatCode") or x.get("shotCode")) == beat), None)
        if not b:
            print(json.dumps({"error": "beat not found: " + beat})); return
        if kind == "seedance":
            # seedancePromptOverride RETIRED (2026-07-07, Julian's Studio-editing feature): this branch used to
            # surface a manual override verbatim, but it was already permanently unreachable (_is_def was hardcoded
            # True — cb_segprompt.for_beat is the definitive prose for EVERY beat and always wins), and the write
            # side (the Studio's "Save & use this exact prompt" button) is gone now too. Editing happens on the
            # beat's own cuts[] (the Studio's shots editor) — see cb_beats.gate3_prepare's docstring.
            # SOURCE OF TRUTH: cb_segprompt DEFINITIVE prose (segment beats) or the cb_seedance compact (never the old JSON builder).
            g = cb_seedance.get_seedance_prompt(os.path.join("..", "cb-output", pkg), beat, mode="export", episode=episode)
            print(json.dumps({"kind": "cb_seedance compact render prompt", "builder": g["builder"], "format": g.get("format"),
                              "prompt": g["prompt"], "readiness_status": g["readiness_status"],
                              "hard_fails": g["hard_fails"], "warnings": g["warnings"]}))
            return
        # kind == "keyframe" — the SAME resolver generation uses → card == API.
        prompt, refs, info = cb_scene.keyframe_for(beats, beat, episode)
        print(json.dumps({"kind": info.get("kind"), "prompt": prompt, "chain": info.get("chain"),
                          "refs": [os.path.basename(str(r)) for r in refs], "refCount": len(refs)}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

main()
