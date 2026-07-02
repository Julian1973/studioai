#!/usr/bin/env python3
"""Print the ACTUAL directed ElevenLabs V3 voice lines for a beat — the acted text (with tags) that cb_voice
feeds to ElevenLabs, so the studio card shows what-you-hear-is-what-you-edit. NO synthesis (no API cost).
Usage: python3 voice_preview.py <beat_package.json> <beatCode> [episode]   (run from cb-gen/)"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE); sys.path.insert(0, HERE)
import cb_voice as V

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: voice_preview.py <package> <beatCode> [episode]"})); return
    pkg, beat = sys.argv[1], sys.argv[2]
    try:
        d = json.load(open(os.path.join("..", "cb-output", pkg)))
        beats = d.get("beats") or d.get("shots") or []
        b = next((x for x in beats if str(x.get("beatCode") or x.get("shotCode")) == beat), None)
        if not b:
            print(json.dumps({"error": "beat not found: " + beat})); return
        if b.get("wordlessHeld"):
            print(json.dumps({"script": "", "lines": [], "overridden": False,
                              "note": "wordless-held beat — silence carries it (no voice)"})); return
        ovr = (b.get("voiceScript") or "").strip()
        if ovr:
            lines = []
            for ln in [l for l in ovr.splitlines() if l.strip()]:
                for lab, txt in V._cut_segments(V._upcase_leading_label(ln.strip())):   # case-insensitive labels (match the render)
                    lines.append({"character": V._resolve_speaker(lab, b) or (lab or ""), "text": txt})
            print(json.dumps({"script": ovr, "lines": lines, "overridden": True})); return
        # build the DIRECTOR-LED lines from the cuts (NO synthesis — text only). The studio card shows the SAME acting
        # the render voices: the director's acted line (V3 tags for the cadence/arc) per line, else keyword fallback.
        ep = sys.argv[3] if len(sys.argv) > 3 else "Ep1"
        try:
            import cb_seedance as S
            vd = V._voice_dir_lookup(S.director_voice_direction(os.path.join("..", "cb-output", pkg), beat, ep))
        except Exception:
            vd = {}
        lines = []
        for c in [c for c in (b.get("cuts") or []) if (c.get("dialogue") or "").strip()]:
            for lab, line in V._cut_segments(c.get("dialogue")):
                speaker = V._resolve_speaker(lab, b)
                if not (speaker and line):
                    continue
                text = vd.get((speaker.lower(), V._norm_words(line))) \
                       or V.direct_line(speaker, shot={"performance": {"surface": c.get("delivery", "")}, "intent": {}}, raw=line)
                if text:
                    lines.append({"character": speaker, "text": text})
        script = "\n".join(f"{l['character']}: {l['text']}" for l in lines)
        print(json.dumps({"script": script, "lines": lines, "overridden": False, "director_led": bool(vd)}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

main()
