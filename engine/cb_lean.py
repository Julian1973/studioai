#!/usr/bin/env python3
"""cb_lean.py — THE LEAN ENGINE (Julian, 2026-07-25: "ok lets start again").

WHY THIS EXISTS. The engine it stands beside is 10,468 lines and feeds a 6,711-word
curriculum to produce one prompt. In one evening it produced: a charge that contradicted
its own schema, a hash that depended on the caller's working directory, a word budget with
an escape clause underneath it that nothing could fail, and a guardrail removed an hour
after being added. None of that is a rules problem. It is a volume problem — rules
accreted with no mechanism for retirement, until they disagreed with each other.

WHAT THIS IS. The same five stages, a fifth of the machinery, in a different order:

    script -> cards -> [THE LAW + ONE EXEMPLAR] -> prompt -> fire -> verdict -> corpus

THE ONE RULE ABOUT RULES. Nothing goes in THE LAW that a worked exemplar could teach by
example, and nothing goes in that was not paid for by a real fire and a real verdict.
Every line in LEAN_LAW.md can name the take that bought it. When a new law is proposed,
it must name the law it replaces — the list does not grow by default.

WHAT THIS DELIBERATELY DOES NOT DO:
  * no structured continuity. AnyFilm ship AAA footage with no state machine at all —
    continuity is a phrase inside the action sentence ("still dusted in pollen"). Our
    apparatus is what welded Zenny to a flower while the same prompt had her hovering.
  * no context hashing. Freshness is the approved prompt's own text vs the card's own
    text. Two strings. It cannot depend on which directory the process runs from.
  * no checks written ahead of footage. The corpus earns them.

WHAT IT KEEPS, BECAUSE THESE WERE PROVEN, NOT ASSUMED: the gates (a human signs, nothing
self-advances), reference-first identity, V3 as the sole voice, one auteur per chair.

This module compiles. It does not spend. Firing stays in the existing, gated path until
this engine has earned the swap on real footage.
"""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
CRAFT = HERE.parent / "shows" / "crystal-bears" / "creative"
LAW = CRAFT / "LEAN_LAW.md"


def law():
    """THE LAW, read fresh every call — an edit reaches the very next prompt."""
    return LAW.read_text(encoding="utf-8")


def exemplar(form="physical_comedy"):
    """The worked winner for THIS dramatic form, or None.

    None is a real answer and is handed over as one. A formula proven on crashes teaches a
    quiet interior beat to fill stillness with impacts — the failure Julian named as
    "clunky, scripted, fake". A missing exemplar costs one exploratory take; a wrong one
    silently teaches the wrong shape on every future beat of that form."""
    import cb_formulas
    # A REGISTRY KEY IS NOT A DRAMATIC FORM. The library resolves free text ("physical
    # comedy, escalating") by keyword; a registry key ("physical_comedy") matches nothing,
    # so passing one silently returned "no exemplar" — the writer would have been told to
    # discover a formula that already exists, on the one form we have actually proven.
    # Caught on the first side-by-side run, before it reached a fire.
    _, meta = cb_formulas.formula_block(str(form or "").replace("_", " "))
    if not meta.get("exemplar"):
        return None
    p = CRAFT / meta["exemplar"]
    return p.read_text(encoding="utf-8") if p.exists() else None


def brief(card):
    """The card's own facts, as facts. No prose, no scaffolding, no invention.

    Everything here is authored by a human at Gate 1 and merely transcribed. If a field is
    empty it is omitted — never defaulted, never filled with a generic sentence. That
    substitution is how "any temporary marks or wardrobe" ended up in shipped prompts."""
    rows = [("SHOT", card.get("shotId")),
            ("BEAT", card.get("storyBeat") or card.get("summary")),
            ("OPENS ON", card.get("openingPose")),
            ("ACTION", card.get("physicalStaging")),
            ("PAYOFF", card.get("visualPayoff")),
            ("ENDS BY", card.get("endingBehaviour")),
            ("CARRIES IN", card.get("carryMarks") or card.get("continuityProseIn")),
            ("CAST", ", ".join(card.get("charactersInFrame") or []))]
    return "\n".join(_render(k, v) for k, v in rows if v)


def _render(key, value):
    """A card field as readable English. physicalStaging is a nested object on a real card
    (staysVisible / contactAndWeight / payoffShape / prohibitedStaging) and str()-ing it
    put raw Python dict syntax in front of the writer — caught on this module's first run,
    before it ever reached a prompt."""
    if isinstance(value, dict):
        inner = "\n".join(f"  - {_label(k)}: {_flat(v)}" for k, v in value.items() if v)
        return f"{key}:\n{inner}"
    return f"{key}: {_flat(value)}"


def _flat(v):
    if isinstance(v, (list, tuple)):
        return "; ".join(str(x).strip() for x in v if x)
    return str(v).strip()


def _label(k):
    """staysVisible -> stays visible. The card's own field names, made readable."""
    return re.sub(r"(?<!^)(?=[A-Z])", " ", str(k)).lower()


def charge(card, form="physical_comedy"):
    """What the writer is given: THE LAW, one worked winner, and this card's facts.

    That is the whole brief. If the writer needs more than this to write the shot, the
    missing thing belongs on the card — authored by a human — not in a longer charge."""
    ex = exemplar(form)
    parts = [law()]
    if ex:
        parts.append("===== A REAL PROMPT THAT PRODUCED AN APPROVED TAKE ON THIS KIND OF "
                     "MATERIAL =====\nStudy HOW IT IS JOINED — one physical cause, every "
                     "later event a consequence of it, the object of one sentence "
                     "becoming the subject of the next, the biggest travel inside a "
                     "spoken section. Its length is NOT a target: a rejected prompt in "
                     "the same corpus sits within six words of it. Match the causal "
                     "structure, not the size. Do not copy its content.\n\n" + ex)
    else:
        parts.append("===== NO PROVEN EXEMPLAR FOR THIS FORM YET =====\nYou are "
                     "discovering one. Write what this material actually needs. If the "
                     "take is approved, your prompt becomes this form's exemplar.")
    parts.append("===== THIS SHOT =====\n" + brief(card))
    return "\n\n".join(parts)


# ── THE ONLY MEASUREMENTS THAT EARNED THEIR PLACE ──────────────────────────────────────
# Both come from real prompts with real verdicts, and both are ADVISORY. A machine
# refusing a prompt on rhythm is how a pipeline produces compliant work nobody watches.
STASIS = ("hold", "holds", "held", "settle", "settles", "settled", "settling", "anchor",
          "anchored", "still", "stillness", "motionless", "steady", "static", "remains",
          "remain", "stays", "stay", "two-shot", "locked")
KEEPER_STASIS_PER_100 = 1.94      # measured: SH1_KEEPER_EXEMPLAR.txt (approved)
KEEPER_WORDS = 722                # the best take so far — not a target, not a ceiling
ANYFILM_DELIVERED = 244           # their own stated per-clip average


def measure(prompt_text):
    """What this prompt IS, against the only two prompts we have real verdicts on."""
    w = len((prompt_text or "").split()) or 1
    low = (prompt_text or "").lower()
    hits = [t for t in STASIS for _ in re.findall(r"\b" + re.escape(t) + r"\b", low)]
    return {"words": w,
            "stasisPer100": round(len(hits) / w * 100, 2),
            "keeperStasisPer100": KEEPER_STASIS_PER_100,
            "keeperWords": KEEPER_WORDS,
            "anyfilmDelivered": ANYFILM_DELIVERED,
            "notes": _notes(w, len(hits) / w * 100, low)}


def _notes(words, density, low):
    out = []
    if density > 2.6:
        out.append(f"stasis {density:.2f}/100 vs the approved keeper's "
                   f"{KEEPER_STASIS_PER_100} — a shot told repeatedly to settle will settle")
    for t in ("two-shot", "hold", "anchored"):
        n = len(re.findall(r"\b" + re.escape(t) + r"\b", low))
        if n >= 3:
            out.append(f"'{t}' x{n} — a repeated lock becomes the shot's main instruction")
    # THE LENGTH NOTE IS DELETED (2026-07-26, CREATIVE OVER CONSTRAINTS — CLAUDE.md rule 87).
    # It fired on `words > 400`, and measured against the whole verdict corpus that is 3 of 3:
    # the 722-word APPROVED keeper, the 611-word cause-chain build (the best prompt we have)
    # and the 810-word rejection alike. Zero discrimination, headlined by a word count — the
    # same inversion that retired the intent Stop, sitting live in an advisory. Length is not
    # the variable; stop-command density is (keeper 1 stop phrase per 722w; the rejects 9 and
    # 10 at 716w and 810w). The stasis note above KEEPS its place — it at least separates
    # these three (1.94 / 1.96 / 3.21) — but per e0e6bd9 the broad term list overlaps across
    # the wider corpus (GOOD 1.94-2.24, BAD 2.09-3.21), so it stays a smoke alarm, never a gate.
    return out


if __name__ == "__main__":
    import sys
    pkg = json.loads((HERE.parent / "shows" / "crystal-bears" / "episodes" / "output" /
                      "Ep1_scene1_production_package.json").read_text())
    sid = sys.argv[1] if len(sys.argv) > 1 else "S1.SH2"
    card = next(s for s in pkg["shots"] if s["shotId"] == sid)
    c = charge(card)
    print(f"CHARGE for {sid}: {len(c.split())} words "
          f"(the engine it replaces feeds 6,711 of curriculum alone)\n")
    print(brief(card))
