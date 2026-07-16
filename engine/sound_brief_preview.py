#!/usr/bin/env python3
"""Print a beat's INFORMATIONAL sound brief — cb_prompts._music_line + _sfx_line — for the studio to display
+ audit (mirrors beat_preview.py/voice_preview.py). READ-ONLY: this is scratch/advisory text for a human to
read, never fed into the shipped Seedance render prompt (the v5 engine deliberately keeps per-beat music/SFX
direction OUT of the render prompt for word-budget reasons — see CLAUDE.md rule 42). No API cost.
Usage: python3 sound_brief_preview.py <beat_package.json> <beatCode> [episode=Ep1]   (run from engine/)"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE); sys.path.insert(0, HERE)
import cb_prompts as P

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: sound_brief_preview.py <package> <beatCode> [episode]"})); return
    pkg, beat = sys.argv[1], sys.argv[2]
    try:
        d = json.load(open(os.path.join("..", "cb-output", pkg)))
        beats = d.get("beats") or d.get("shots") or []
        b = next((x for x in beats if str(x.get("beatCode") or x.get("shotCode")) == beat), None)
        if not b:
            print(json.dumps({"error": "beat not found: " + beat})); return
        print(json.dumps({"music": P._music_line(b), "sfx": P._sfx_line(b)}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

main()
