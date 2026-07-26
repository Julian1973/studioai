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
# WHICH FIELDS THE STOP MAY REFUSE ON — calibrated 2026-07-25 against four real prompts
# with real recorded verdicts, not chosen by argument:
#     SH1_KEEPER_EXEMPLAR (Julian APPROVED)      must PASS
#     SH2_intent_delivered (built to the intent)  must PASS
#     SH2_old_engine_716w (rejected)              must STOP
#     SH2_LABOURED_FIXTURE (rejected)             must STOP
# Gating every field scored 3/4 — it REFUSED THE APPROVED KEEPER on five tempoDesign
# clauses the keeper genuinely delivers in its own words ("bounce" for "uncontrolled
# bounce", "push" for "dolly", "blink"/"proud" for "stillness before pride"). A false
# refusal on approved work is the worst failure this gate can have: it stops the studio.
# Gating visualPayoff + feltIntent alone scored 4/4.
#   visualPayoff is what must be ON SCREEN, in the Director's own words — word overlap is
#     a fair test of it, and a payoff absent from the prompt is genuinely absent.
#   feltIntent names the beat's purpose, usually with concrete anchors ("the grin held
#     too long").
#   tempoDesign, dramaticIntent, emotionMechanic and doesItLand describe RHYTHM and
#     READING — real direction, delivered through pacing a word-match cannot see. They
#     stay in the writer's charge and in every report, marked advisory, and Julian's eye
#     judges them. Never silently dropped; deliberately not machine-refusable.
GATED_FIELDS = ("visualPayoff", "feltIntent")

# A clause whose subject is the AUDIENCE is the Director describing the intended
# reading — "kids get a bigger crash; adults get the joke that his bravado doesn't know
# the difference." A prompt delivers that through the staging itself; it can never
# contain those words, and hard-gating them would refuse every good take (proven
# 2026-07-25: the APPROVED SH1 keeper misses every audience-read clause while landing
# all of them on screen). These stay in the writer's charge and the report — marked
# "judged by eye" — but the Stop never refuses on them.
_AUDIENCE = re.compile(r"\b(the audience|audiences|kids get|adults get|kids see|"
                       r"adults see|viewers?)\b", re.I)

_DEMAND = re.compile(r"\b(drives?|lands?|held|hold|stays?|keeps?|reads?|carries|"
                     r"builds?|slows?|quickens?|breaks?|settles?|escapes?|betrays?|"
                     r"believes?|treats?|preens?|beams?|grins?|smiles?|pauses?|"
                     r"gentle|unhurried|playful|alive|flat|calm|sincere|delighted|"
                     r"gleeful|ridiculous|official|comedy|joke|hinge|button|beat)\b", re.I)


def intent_of(shot):
    """The Director's stated purpose, verbatim, field by field. Never paraphrased."""
    return {k: str(shot.get(k)).strip() for k in INTENT_FIELDS
            if shot.get(k) and str(shot.get(k)).strip()}


def _cast_words(shot):
    """The shot's OWN cast names — never a demand a prompt can fail.

    Every reference-anchored prompt binds each character by name by construction
    ("Fuzzby is the character from @图3"), so a clause term of "Fuzzby" or "Fuzzby's" is a
    GUARANTEED hit that discriminates nothing and dilutes the clause's real demands. On a
    4-term clause it is worth 25% — enough to tip a genuinely rejected prompt over the 0.5
    threshold on an exact tie, which is exactly how SH2_LABOURED started passing
    (measured, 2026-07-26).
    """
    out = set()
    for n in (shot.get("charactersInFrame") or []):
        for w in re.findall(r"[a-z][a-z'-]{2,}", str(n).lower()):
            out.add(w.rstrip("'s"))
    return out


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
            # visualPayoff is a demand BY DEFINITION — it is the Director's own named
            # payoff, and every word of it is what must be on screen. The _DEMAND filter
            # exists to drop scene-setting prose from the feeling/tempo fields; applied to
            # the payoff it silently dropped the WHOLE payoff on real shots (S1.SH3/SH5,
            # found 2026-07-25: "swallowed", "smiling", "sigh" weren't in the verb list, so
            # the Stop never enforced the payoff at all). Payoff clauses always count.
            if len(c.split()) < 3 or (field != "visualPayoff" and not _DEMAND.search(c)):
                continue
            terms = [w for w in re.findall(r"[a-z][a-z'-]{2,}", c.lower())
                     if w not in _STOP and w.rstrip("'s") not in _cast_words(shot)]
            if terms:
                out.append({"field": field, "clause": c, "terms": terms,
                            "gated": field in GATED_FIELDS and not _AUDIENCE.search(c)})
    return out


def _covered(term, prompt_low):
    """Is this demand present in the prompt? Stem-tolerant, so 'grins' honours 'grin' and
    'slows' honours 'slow' — a Director writing 'slows into the discovery' is satisfied by a
    prompt that decelerates, not only by one that repeats her verb."""
    # Stem down past plural AND participle endings — the Director writing "smiling" is
    # satisfied by a prompt whose character "smiles", and vice versa. "smiles?" alone
    # missed "smiling" (found on S1.SH5, 2026-07-25). Keep the stem >= 4 chars so short
    # words never over-match.
    t = term
    # "Fuzzby's" must be satisfied by a prompt that says "Fuzzby" — found live, 2026-07-26,
    # when a real production prepare hard-stopped twice on a clause demanding the literal
    # token "fuzzby's". A possessive is the same word.
    if t.endswith("'s") or t.endswith("\u2019s"):
        t = t[:-2]
    for suf in ("ing", "ed", "es", "s"):
        if len(t) - len(suf) >= 4 and t.endswith(suf):
            t = t[:-len(suf)]
            break
    return re.search(r"\b" + re.escape(t), prompt_low) is not None


def _staging_text(shot):
    """Everything the beat itself says is physically STAGED — the vocabulary a writer
    actually has to build from."""
    bits = [str(shot.get(k) or "") for k in
            ("performanceAssignment", "openingPose", "camera", "physicalStaging",
             "storyBeat", "summary", "visualPayoff", "continuityProseIn")]
    for c in (shot.get("cuts") or []):
        if isinstance(c, dict):
            bits += [str(c.get("action") or ""), str(c.get("framing") or "")]
    return " ".join(bits).lower()


def _deliverable(clause, shot):
    """NOT WIRED INTO score() — built 2026-07-26, measured, and found not to do its job.

    The idea was sound and the problem is real (below). The implementation is not: on the
    very clause that motivated it — "Fuzzby's showmanship physically betrays him" — it
    returns True, because "physically" happens to appear in the beat's own physics text.
    So it exempts nothing it was built to exempt. Left here, unwired and labelled, because
    the PROBLEM it names is real and still open; a future attempt should start from this
    measurement rather than rediscover it. Do not wire it up without re-measuring against
    the four-prompt calibration set in GATED_FIELDS' own note.

    THE PROBLEM IT WAS FOR. Can a prompt deliver this clause AS WORDS at all?

    A Director writes feltIntent in two registers at once. Some of it is staged and
    filmable — "the crash stamps him with a ridiculous golden-pollen moustache... he
    preens, he's delighted". Some of it states what the beat MEANS — "Fuzzby's showmanship
    physically betrays him". The second is delivered by staging the first; no prompt
    contains the word "betrays", and demanding it hard-stopped a real production prepare
    twice on 2026-07-26 with the writer having done nothing wrong.

    The test is mechanical and grounded in the beat's OWN data, never a word list of
    "abstract" terms: does ANY of the clause's vocabulary appear anywhere in what this beat
    itself describes as staged? If the Director's words for a clause appear nowhere in her
    own staging, she is naming a meaning, not a shot — so it is advisory, and her eye
    judges whether the staging carries it."""
    stage = _staging_text(shot)
    return any(_covered(t, stage) for t in clause["terms"])


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
    missed = [r for r in rows if not r["met"]]
    return {"clauses": rows,
            "total": len(rows),
            "met": len(met),
            # "missed" stays ALL misses (the report shows everything); the Stop refuses
            # only on the gated subset — an audience-read clause is judged by eye.
            "missed": missed,
            "missedGated": [r for r in missed if r.get("gated", True)],
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
    # THE RECEIPT SCHEMA (2026-07-26). judge() had never been run — it called
    # cb_llm.structured without the required `schema` argument and would have crashed.
    # The point of this call is not a score; it is that the reader must POINT AT the
    # sentence carrying each of the Director's clauses. A verdict with no quotable
    # sentence is an admission the beat is not there, and one with a quote is something
    # Julian can check in two seconds. That is the whole difference from word-matching:
    # wrong here is VISIBLE.
    from pydantic import BaseModel, Field
    from typing import List, Literal

    class ClauseVerdict(BaseModel):
        clause: str = Field(description="the Director's clause, quoted from her own words")
        verdict: Literal["DELIVERED", "PARTIAL", "ABSENT"]
        deliveringSentence: str = Field(
            description="the EXACT sentence from the prompt that delivers it, verbatim; "
                        "empty string if no sentence does")

    class IntentReceipt(BaseModel):
        clauses: List[ClauseVerdict]
        absentCount: int
        oneLineVerdict: str = Field(description="does this prompt land the beat — one sentence")

    return cb_llm.structured(sys_p, usr, IntentReceipt, model=model, label="intent_judge")


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
