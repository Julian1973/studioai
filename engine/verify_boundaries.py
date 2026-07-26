#!/usr/bin/env python3
"""verify_boundaries.py — AUDIT A BREAKDOWN'S OWN BOUNDARY REASONING (2026-07-26).

Born out of a blind three-way adjudication of the same script broken down by two
different authors. Three independent judges split on one question and only one: is a
boundary reason actually VERIFIABLE, or merely persuasive? One judge said the numbered
event citations were unfalsifiable to a reader; another said they were the only
falsifiable thing on the page. Both were half right — the citations are checkable, the
document just never carried the evidence to check them against.

So this checks them. Every "event N" a boundaryReason cites is resolved against the real
mechanical parse: does that event exist, is it in the beat's own scene, and what does it
actually say. It never judges whether the REASONING is good — that is Julian's own
verdict and no check should approximate it. It answers the one question a machine can:
is the claim true.

    python3 verify_boundaries.py <breakdown.json> [Ep1]
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_intake


def verify(path, episode="Ep1", log=print):
    d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    src = cb_intake.script_path_for(episode)
    events = cb_intake.parse_script(src.read_text(encoding="utf-8"),
                                    log=lambda *a, **k: None)["events"]
    by_i = {e.get("i"): e for e in events}

    beats = d.get("beats", [])
    cited, wrong, uncited = [], [], []
    for b in beats:
        reason = (b.get("boundaryReason") or "").strip()
        idxs = [int(m) for m in re.findall(r"event (\d+)", reason)]
        if not idxs:
            uncited.append(b.get("beatCode"))
            continue
        for i in idxs:
            e = by_i.get(i)
            rec = {"beat": b.get("beatCode"), "scene": b.get("sceneNumber"), "event": i,
                   "exists": e is not None,
                   "eventScene": e.get("scene") if e else None,
                   "text": (e.get("text") or "")[:70] if e else None}
            cited.append(rec)
            if e is None or e.get("scene") != b.get("sceneNumber"):
                wrong.append(rec)

    log(f"{pathlib.Path(path).name}")
    log(f"  {len(beats)} beats · {len(cited)} event citations · "
        f"{len(beats) - len(uncited)}/{len(beats)} beats cite an index")
    for r in cited:
        mark = "OK " if r not in wrong else "BAD"
        log(f"   {mark} {r['beat']:9} event {r['event']:<4} "
            f"{'missing' if not r['exists'] else 'scene ' + str(r['eventScene'])}"
            f" | {r['text'] or ''}")
    if wrong:
        log(f"  FALSE CITATIONS: {len(wrong)} — a boundary argued against an event that is "
            f"not there or not in this scene")
    else:
        log("  every citation resolves to a real event in the beat's own scene")
    if uncited:
        log(f"  no index cited ({len(uncited)}): {', '.join(str(c) for c in uncited[:12])}"
            f"{' …' if len(uncited) > 12 else ''}")
        log("  -> these boundaries can be read, but not checked")
    return {"beats": len(beats), "citations": len(cited), "false": len(wrong),
            "uncited": uncited}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    r = verify(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "Ep1")
    raise SystemExit(1 if r["false"] else 0)
