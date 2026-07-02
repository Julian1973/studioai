#!/usr/bin/env python3
"""Print the ACTUAL assembled keyframe prompt for a beat — the exact string build_keyframe_prompt()
sends to the image generator (so the studio card shows what-you-see-is-what-generates).
Usage: python3 kf_preview.py <beat_package.json> <beatCode> [episode]   (run from cb-gen/)"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE); sys.path.insert(0, HERE)
import cb_prompts as P, cb_scene

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
        prompt, refs, info = cb_scene.keyframe_for(beats, beat, episode)   # the SAME call generation uses → card == API
        print(json.dumps({"kind": info.get("kind"), "prompt": prompt, "chain": info.get("chain"),
                          "refs": [os.path.basename(str(r)) for r in refs], "refCount": len(refs)}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

main()
