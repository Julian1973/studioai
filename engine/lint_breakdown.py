#!/usr/bin/env python3
"""lint_breakdown.py — ADVISORY NOTES ON A STEP-1 BREAKDOWN (2026-07-26).

Every check here came from a blind five-way adjudication of two real breakdowns of the
same script. The judges preferred one of them — but the useful output was not the verdict,
it was the three concrete, checkable defects they found in the breakdown they preferred.
Those are what this file catches.

ADVISORY ONLY. Nothing here blocks, refuses, or caps anything, and nothing here is a gate.
CREATIVE OVER CONSTRAINTS: a note is printed for a human to weigh, and a beat that earns
its flag is free to keep it. The three notes:

1. AUDIENCE-EFFECT CLAIM — "every adult in the room", "the whole audience has been
   waiting". Unfalsifiable, and it is the writer marking their own homework. This studio
   already ruled the same thing for vision QA: name the concrete, checkable feature, never
   assert the reaction. adultRead should say what is VISIBLE and let the room react.

2. OFF-SCREEN CONTENT — "just outside the frame", "off-screen", "we never see". A real
   production risk, not a style note: a beautiful line about a mother standing on a dock
   outside the frame is something a board artist downstream will try to draw.

3. INSTRUCTIONAL NEED — the sharpest of the three. A need the character does not know
   they have cannot be phrased as an obligation they ought to meet. "He needs to accept
   that a plan can fail" is a curriculum objective wearing a character's name; "he needs
   her to keep watching" is a lack he is carrying. The grammar is the tell, and the
   grammar is checkable.

    python3 lint_breakdown.py <breakdown.json>
"""
import json
import pathlib
import re
import sys

# "the whole audience", "every parent in the room", "only the parents watching" — a claim
# about how people will react, which no frame can prove and no chair downstream can stage.
AUDIENCE = re.compile(
    r"\b(every|the whole|all the|any|only the)\s+"
    r"(adult|parent|grown[- ]?up|viewer|audience|room)\w*\b"
    r"|\baudience (has|have|will|is|are)\b"
    r"|\bin the room\b", re.I)

# content the camera cannot see. A board artist will try to draw it.
OFFSCREEN = re.compile(
    r"\b(outside|off)[- ]the[- ]frame\b|\boff[- ]screen\b|\bout of frame\b"
    r"|\bwe (never|don'?t|do not) see\b|\bunseen\b", re.I)

# NEED written as an instruction to the character rather than a lack they carry.
INSTRUCTIONAL = re.compile(
    r"\bneeds? to (accept|recognise|recognize|learn|understand|realise|realize|admit|"
    r"discover|let|allow|stop|trust|respect|remember)\b", re.I)

CHECKS = (("AUDIENCE-EFFECT", AUDIENCE, ("adultRead", "kidRead", "emotionalIntent"),
           "asserts how the room will react — say what is visible instead"),
          ("OFF-SCREEN", OFFSCREEN, ("adultRead", "kidRead", "storyBeat", "emotionalIntent"),
           "names something the camera cannot see — a board artist will try to draw it"),
          ("INSTRUCTIONAL-NEED", INSTRUCTIONAL, ("need",),
           "reads as a lesson the character ought to learn, not a lack they are carrying"))


def lint(path, log=print):
    beats = json.loads(pathlib.Path(path).read_text(encoding="utf-8")).get("beats", [])
    found = []
    for b in beats:
        for name, rx, fields, why in CHECKS:
            for f in fields:
                v = (b.get(f) or "").strip()
                m = rx.search(v)
                if m:
                    found.append({"beat": b.get("beatCode"), "check": name, "field": f,
                                  "hit": m.group(0), "why": why, "text": v})
    log(f"{pathlib.Path(path).name} — {len(beats)} beats, {len(found)} advisory note(s)")
    for name, _, _, _ in CHECKS:
        rows = [r for r in found if r["check"] == name]
        log(f"\n  {name}  ({len(rows)})")
        for r in rows:
            log(f"    {r['beat']:9} {r['field']:8} “{r['hit']}”")
            log(f"              {r['text'][:150]}")
    log("\n  Advisory only. Nothing here blocks or refuses. A beat that earns its "
        "flag keeps it.")
    return found


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    lint(sys.argv[1])
