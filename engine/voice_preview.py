#!/usr/bin/env python3
"""Print the ACTUAL directed ElevenLabs V3 voice lines for a beat — the acted text (with tags) that cb_voice
feeds to ElevenLabs, so the studio card shows what-you-hear-is-what-you-edit. NO synthesis (no API cost).
Usage: python3 voice_preview.py <beat_package.json> <beatCode> [episode]   (run from engine/)"""
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
            # read_only=True (2026-07-15): this script's own docstring already promises "NO synthesis, no API
            # cost" — but director_voice_direction had no way to honour that promise once a beat's cuts[] text
            # changed and its Director's Pass cache went stale: it would silently fire a real, ~40-60s LLM call
            # to re-direct the beat just to show this preview. Never regenerate from a preview card.
            vd = V._voice_dir_lookup(S.director_voice_direction(os.path.join("..", "cb-output", pkg), beat, ep, read_only=True))
        except Exception:
            vd = {}
        # FIXED 2026-07-12 (full-codebase audit continued): this used to hand-roll cut-segment iteration + speaker
        # resolution + a stripped-down shot dict ({"performance": {"surface": ...}, "intent": {}}) straight into
        # direct_line() — missing every BEAT-level field _is_tender()/_leak() actually read (emotionalIntent,
        # crystalGlow, crystalTruth, need, performance.underneath/innerThought), so a genuinely tender/Crystal-Call
        # line could never get its [quietly] tag or need-leak breath in THIS preview even though the real render
        # (cb_voice.build_dialogue_track, via the identical _resolve_turns) gets it right — the preview silently
        # disagreed with what actually ships. It also had no group_chorus handling at all, so a chorus cut (e.g.
        # 8.B3's "ALL:" line) misattributed to a fabricated 'All' pseudo-character instead of showing the real
        # GROUP_CHORUS asset the render actually builds. Now calls the SAME shared resolver
        # (cb_voice._resolve_turns) build_dialogue_track uses in production, so the card is genuinely WYSIWYG.
        try:
            turns = V._resolve_turns(b, vd)
        except SystemExit as e:                 # _resolve_turns fails loud on a speaker with no canonical voiceId
            print(json.dumps({"error": str(e)})); return
        lines = [{"character": t["character"], "text": t["text"]} for t in turns]
        script = "\n".join(f"{l['character']}: {l['text']}" for l in lines)
        print(json.dumps({"script": script, "lines": lines, "overridden": False, "director_led": bool(vd)}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

main()
