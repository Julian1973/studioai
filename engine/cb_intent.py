#!/usr/bin/env python3
"""cb_intent.py — THE INTENT ENGINE (Julian's ruling, 2026-07-25).

His question, which exposed the whole gap: *"what are you trying to achieve in this scene,
what is the purpose of the beat — and does the prompt deliver it? You have the director who
puts together an amazing shot, but do you as the prompt creator deliver for the director?"*

The honest answer was no. Every prompt this studio has written was checked against a FAILURE
LIST — no geometry, no body-in-flower, no stasis, identity held. Not one check ever asked
whether the text delivered the thing the Director said the beat was FOR. So S1.SH2's card
says the comedy hinge is *"the grin held too long"*, and the prompt written against nine
passing checks contained no grin at all.

THE RULE THIS MODULE ENFORCES: the Director's stated purpose is the specification. The
prompt is an implementation of it. An implementation that omits a clause of the spec is
incomplete no matter how clean its physics.

    Director's beat  ──>  intent clauses  ──>  the writer's charge
                                │
    compiled prompt  ──────────┴──>  coverage score  ──>  gaps, named verbatim

WHY CLAUSE COVERAGE AND NOT A TASTE SCORE. A model asked "does this deliver the intent?"
says yes to almost anything — this project has the receipts (a vision check waved through
two known-bad keyframes until it was rewritten to ask concrete questions instead). So the
zero-cost core is mechanical and unarguable: every clause the Director wrote is either
represented in the prompt or it is not, and the ones that are not are printed in his own
words. `judge()` adds the semantic read on top, but only as a second opinion, and it can
never overturn a missing clause.
"""
import os
import re

# The fields where a Director states PURPOSE rather than facts. Ordered by how load-bearing
# they proved across 42 recorded verdicts: tempo failures ("everything plays at one even
# middle pace", "stale emotions and dead delivery") outnumber every other creative rejection.
INTENT_FIELDS = ("feltIntent", "tempoDesign", "visualPayoff", "dramaticIntent",
                 "emotionMechanic", "doesItLand")

# Words that carry no requirement — stripped before a clause is reduced to its demands.
_STOP = set("""a an and are as at be been being both but by can could did do does for from
had has have he her here hers him his how i if in into is it its itself just me more most
my no nor not of off on once only or other our out over own same she should so some such
than that the their them then there these they this those through to too under until up
very was we were what when where which while who whom why will with would you your it's
their own each every into onto while during before after between within""".split())

# A clause is only a real requirement if it demands something. These are the verbs and
# qualities a Director uses to specify feel; a clause with none of them is scene-setting.
_DEMAND = re.compile(r"\b(drives?|lands?|held|hold|stays?|keeps?|reads?|carries|"
                     r"builds?|slows?|quickens?|breaks?|settles?|escapes?|betrays?|"
                     r"believes?|treats?|preens?|beams?|grins?|smiles?|pauses?|"
                     r"gentle|unhurried|playful|alive|flat|calm|sincere|delighted|"
                     r"gleeful|ridiculous|official|comedy|joke|hinge|button|beat)\b", re.I)


def intent_of(shot):
    """The Director's stated purpose, verbatim, field by field. Never paraphrased."""
    return {k: str(shot.get(k)).strip() for k in INTENT_FIELDS
            if shot.get(k) and str(shot.get(k)).strip()}


def clauses(shot):
    """The purpose, decomposed into individually checkable requirements.

    A Director writes intent as prose — 'his joy drives the speed; the grin-held-too-long
    beat is the comedy hinge before one sharp impact'. That is two separate demands on the
    prompt, and they must be checkable separately or a missing one hides inside a satisfied
    one. Split on real clause boundaries (sentence, semicolon, em-dash), keep only clauses
    that actually demand something, and reduce each to the content words a prompt would have
    to contain to honour it."""
    out = []
    for field, text in intent_of(shot).items():
        for raw in re.split(r"(?<=[.;])\s+|\s+--\s+|\s+—\s+", text):
            c = raw.strip(" .;—-")
            if len(c.split()) < 3 or not _DEMAND.search(c):
                continue
            terms = [w for w in re.findall(r"[a-z][a-z'-]{2,}", c.lower())
                     if w not in _STOP]
            if terms:
                out.append({"field": field, "clause": c, "terms": terms})
    return out


def _covered(term, prompt_low):
    """Is this demand present in the prompt? Stem-tolerant, so 'grins' honours 'grin' and
    'slows' honours 'slow' — a Director writing 'slows into the discovery' is satisfied by a
    prompt that decelerates, not only by one that repeats her verb."""
    t = term.rstrip("s") if len(term) > 4 else term
    return re.search(r"\b" + re.escape(t), prompt_low) is not None


def score(prompt_text, shot, threshold=0.5):
    """Does the prompt deliver the Director's stated purpose? Zero cost, deterministic.

    Per clause: what fraction of its demands appear in the prompt. Below `threshold` the
    clause is MISSED and reported in the Director's own words — because 'you dropped the
    comedy hinge' is actionable and 'intent coverage 0.62' is not."""
    low = (prompt_text or "").lower()
    rows = []
    for c in clauses(shot):
        hit = [t for t in c["terms"] if _covered(t, low)]
        cov = len(hit) / len(c["terms"])
        rows.append({**c, "coverage": round(cov, 2),
                     "missing": [t for t in c["terms"] if t not in hit],
                     "met": cov >= threshold})
    met = [r for r in rows if r["met"]]
    return {"clauses": rows,
            "total": len(rows),
            "met": len(met),
            "missed": [r for r in rows if not r["met"]],
            "coverage": round(len(met) / len(rows), 2) if rows else None}


def charge(shot):
    """THE WRITER'S BRIEF, LED BY PURPOSE.

    The order is the point. Every previous version of this charge opened with laws and
    buried the beat's purpose in a data field near the bottom; the writer optimised for the
    laws. Here the Director's own words come first, the clauses she must honour are listed
    explicitly, and the laws follow as constraints on HOW — never as the goal."""
    it = intent_of(shot)
    if not it:
        return None
    parts = ["===== WHAT THIS BEAT IS FOR — THE DIRECTOR'S OWN WORDS =====",
             "This is the specification. Your prompt is an implementation of it. Physics, "
             "camera and continuity are how you deliver it — they are never the goal.\n"]
    for k, v in it.items():
        parts.append(f"[{k}]\n{v}\n")
    cl = clauses(shot)
    if cl:
        parts.append("===== EVERY ONE OF THESE MUST BE VISIBLE ON SCREEN =====")
        parts += [f"  {i}. {c['clause']}" for i, c in enumerate(cl, 1)]
        parts.append("\nA prompt that omits one of these is incomplete, however clean its "
                     "physics. If a clause names a beat (a grin held too long, a pause, a "
                     "preen), that beat is written as its own moment — not implied.")
    return "\n".join(parts)


def report(prompt_text, shot):
    """Human-readable verdict — what the Director asked for, and what the prompt gave back."""
    s = score(prompt_text, shot)
    if not s["total"]:
        return "no stated intent on this shot — nothing to deliver against"
    L = [f"INTENT DELIVERY — {s['met']}/{s['total']} clauses met ({int(s['coverage']*100)}%)"]
    for r in s["missed"]:
        L.append(f"\n  MISSED [{r['field']}] — the Director asked for:")
        L.append(f"    “{r['clause']}”")
        L.append(f"    nothing in the prompt for: {', '.join(r['missing'][:8])}")
    if not s["missed"]:
        L.append("  every stated clause is represented in the prompt.")
    return "\n".join(L)


def judge(prompt_text, shot, model=None):
    """SECOND OPINION ONLY — one LLM read asking whether the prompt genuinely DELIVERS the
    intent, not merely mentions its words. Costs a call, so it is never on the default path.

    It can never overturn a missed clause: presence is a fact, delivery is a judgement, and
    a judgement is not allowed to excuse an omission."""
    import cb_llm
    it = intent_of(shot)
    if not it:
        return None
    sys_p = ("You are a film director reading a shot prompt. You are given what the beat is "
             "FOR, in the director's own words, and the prompt written to achieve it. For "
             "each stated intent, answer only: is it DELIVERED, PARTIAL or ABSENT, and quote "
             "the exact sentence from the prompt that delivers it — or say no sentence does. "
             "Do not praise. Do not suggest rewrites. A prompt that describes the mechanics "
             "of an event without its intended feeling is PARTIAL at best.")
    usr = ("DIRECTOR'S INTENT:\n" + "\n".join(f"[{k}] {v}" for k, v in it.items())
           + "\n\nTHE PROMPT:\n" + (prompt_text or ""))
    return cb_llm.structured(sys_p, usr, model=model) if hasattr(cb_llm, "structured") else None


if __name__ == "__main__":
    import json, pathlib, sys
    HERE = pathlib.Path(__file__).resolve().parent
    pkg = json.loads((HERE.parent / "shows" / "crystal-bears" / "episodes" / "output" /
                      "Ep1_scene1_production_package.json").read_text())
    sid = sys.argv[1] if len(sys.argv) > 1 else "S1.SH2"
    shot = next(s for s in pkg["shots"] if s["shotId"] == sid)
    if len(sys.argv) > 2:
        print(report(pathlib.Path(sys.argv[2]).read_text(), shot))
    else:
        print(charge(shot))
