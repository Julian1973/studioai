#!/usr/bin/env python3
"""cb_formulas.py — THE FORMULA LIBRARY (Julian's ruling, 2026-07-25).

The product that ships many episodes is not the rulebook and not the gates. It is a small
set of PROVEN prompt shapes, one per dramatic form, each derived from real fires and each
tagged so it is never applied to material it was not proven on.

Why this module exists, stated plainly: eighty-six prose rules produced one approved shot.
Eleven live A/B fires produced the formula that made it. Rules describe; a worked exemplar
transfers. So the writer is given the WINNER for the form it is actually writing — and,
when no winner exists yet for that form, is told so honestly and asked to discover one,
rather than handed a shape proven on different material and left to mimic it.

Two disciplines, both load-bearing:

  NEVER THE WRONG EXEMPLAR. The physical-comedy formula spends ~720 words because every
  sentence buys physics. Handing that to a quiet interior beat teaches the writer to fill
  a stillness beat with impacts — the exact failure Julian named as "clunky, scripted,
  fake". Resolution is deliberately CONSERVATIVE: an unconfident match resolves to no
  formula (a discovery fire), never to a near-neighbour. A missing exemplar costs one
  exploratory take; a wrong one silently teaches the wrong lesson on every future beat.

  NEVER A FABRICATED EXEMPLAR. A form earns "proven" only when a real take was approved
  under it, and `provenBy` names the evidence. This module will not invent a formula, and
  it will not promote one — `record_proven()` exists so a real approval writes it.
"""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
CRAFT_DIR = HERE.parent / "shows" / "crystal-bears" / "creative"
FORMULA_DIR = CRAFT_DIR / "formulas"
REGISTRY = FORMULA_DIR / "registry.json"


def load_registry():
    """Read fresh every call — a formula promoted mid-session reaches the very next card."""
    if not REGISTRY.exists():
        return {"forms": {}}
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


# ── FORM RESOLUTION ────────────────────────────────────────────────────────────────────
# primaryForm is deliberately FREE TEXT at Gate 3 ("describe what it IS, you are not
# picking from a fixed menu", rule 434) — so the Director's own words have to be mapped
# onto the library. Keyword scoring, not an LLM call: this runs on every authored card and
# must be free, deterministic and inspectable. Ambiguity resolves to None, never a guess.
_SIGNALS = {
    "physical_comedy": ("physical comedy", "slapstick", "pratfall", "crash", "collision",
                        "tumble", "gag", "bumble", "clumsy", "comic chase", "mistimed"),
    "quiet_emotion":   ("quiet emotion", "interior", "stillness", "held", "grief",
                        "realisation", "realization", "tender", "intimate", "reflective",
                        "understated", "melancholy"),
    "two_hander_dialogue": ("dialogue", "exchange", "conversation", "two-hander",
                            "two hander", "banter", "talking", "back and forth"),
    "tension_reveal":  ("tension", "reveal", "suspense", "withheld", "dread", "uneasy",
                        "discovery", "approach"),
    "fast_action":     ("fast action", "urgent", "rescue", "storm", "peril", "stakes",
                        "escape", "kinetic"),
    "wonder_establishing": ("wonder", "establishing", "awe", "vista", "scale", "arrival",
                            "reveal of the world", "majesty"),
    "transition":      ("transition", "bridge", "passage of time", "carries into",
                        "hand-off", "handover", "moves us to"),
}


def resolve_form(primary_form, secondary_colour=None):
    """Free-text dramatic form -> a registry key, or None when it is not clear.

    Returns (key, confidence, why). confidence is 'clear' | 'weak' | 'none'. Only 'clear'
    is ever allowed to hand over an exemplar — see the module docstring on why the
    conservative direction is the safe one."""
    text = f"{primary_form or ''} {secondary_colour or ''}".lower()
    if not text.strip():
        return None, "none", "no dramatic form was stated on this beat"
    # Weight a signal by its own word count: "physical comedy" is a specific two-word
    # phrase, "dialogue" is one generic word. Unweighted counting let two generic words
    # out-vote one specific phrase — caught live on "physical comedy dialogue exchange",
    # which confidently resolved to the dialogue form. A near-tie is not a decision.
    scores = {}
    for key, words in _SIGNALS.items():
        hits = [w for w in words if re.search(r"\b" + re.escape(w), text)]
        if hits:
            scores[key] = (sum(len(w.split()) for w in hits), hits)
    if not scores:
        return None, "none", f"no library form matches {primary_form!r}"
    ranked = sorted(scores.items(), key=lambda kv: kv[1][0], reverse=True)
    top, (top_score, top_hits) = ranked[0]
    if len(ranked) > 1 and ranked[1][1][0] >= top_score:
        close = ", ".join(k for k, (sc, _) in ranked if sc >= top_score)
        return None, "weak", (f"{primary_form!r} matches more than one form equally "
                              f"({close}) — refusing to guess an exemplar")
    return top, "clear", f"matched on {', '.join(top_hits)}"


# ── THE CURRICULUM BLOCK ───────────────────────────────────────────────────────────────
_PROVEN_HEADER = (
    "===== {file} — THE PROVEN FORMULA FOR THIS FORM ({label}) =====\n"
    "This is a REAL prompt that produced an APPROVED take on material of exactly this "
    "kind ({proven_take}; {proven_by}). It is here because it was measured, not because "
    "it is a template — study its SHAPE and its SPEND, then write THIS shot. Every "
    "sentence in it is a physical cause with visible consequences; not one word is spent "
    "on geometry, scaffolding, appearance, or restating the world. Match that level.\n"
    "{notes}\n\n")

_DISCOVERY_BLOCK = (
    "===== NO PROVEN FORMULA EXISTS FOR THIS FORM YET ({label}) =====\n"
    "This beat is {applies}.\n"
    "The house library has a proven formula for physical comedy and NOTHING for this "
    "form. That is deliberate and you are being told rather than handed a substitute: a "
    "shape proven on crashes and mistimed landings is the WRONG lesson for this material, "
    "and borrowing it is how a quiet beat ends up written as a chain of impacts.\n"
    "So this is a DISCOVERY: write what this material actually needs, from the craft laws "
    "and the beat's own facts. Spend words where the experience lives here — which is "
    "probably not where it lives in a crash. If this take is approved, its prompt becomes "
    "this form's formula for every future episode.{notes}\n\n")

_UNRESOLVED_BLOCK = (
    "===== FORM NOT RESOLVED — NO EXEMPLAR SUPPLIED =====\n"
    "{why}. No exemplar is attached, deliberately: handing over a formula proven on "
    "different material would teach the wrong shape. Write from the craft laws and this "
    "beat's own facts.\n\n")


def formula_block(primary_form=None, secondary_colour=None):
    """The curriculum section for THIS beat's form. Returns (text, meta).

    meta records what happened — form key, confidence, whether an exemplar was supplied —
    so the fire record can state which formula (if any) actually produced the prompt.
    That link is what makes the corpus answer 'which formulas are working'."""
    key, conf, why = resolve_form(primary_form, secondary_colour)
    reg = load_registry().get("forms", {})
    meta = {"primaryForm": primary_form, "formKey": key, "confidence": conf,
            "why": why, "exemplar": None, "status": None}

    if key is None or conf != "clear" or key not in reg:
        return _UNRESOLVED_BLOCK.format(why=why.capitalize()), meta

    entry = reg[key]
    meta["status"] = entry.get("status")
    notes = entry.get("notes")
    if entry.get("status") == "proven" and entry.get("exemplar"):
        path = CRAFT_DIR / entry["exemplar"]
        if not path.exists():                       # degrade loudly in meta, not silently
            meta["status"] = "proven-but-missing-file"
            return _UNRESOLVED_BLOCK.format(
                why=f"{key}'s exemplar file {entry['exemplar']} is missing from disk"), meta
        meta["exemplar"] = entry["exemplar"]
        head = _PROVEN_HEADER.format(
            file=entry["exemplar"], label=entry.get("label", key),
            proven_take=entry.get("provenTake", "an approved take"),
            proven_by=entry.get("provenBy", "a real approved fire"),
            notes=(f"\n{notes}" if notes else ""))
        return head + path.read_text(encoding="utf-8"), meta

    return _DISCOVERY_BLOCK.format(
        label=entry.get("label", key),
        applies=entry.get("appliesTo", "of a form with no proven formula yet"),
        notes=(f"\n{notes}" if notes else "")), meta


def record_proven(form_key, exemplar_filename, proven_take, proven_by, notes=None):
    """Promote a form to 'proven' — called when a REAL take is approved, never speculatively.
    Writes the exemplar file from the approved prompt and updates the registry."""
    reg = load_registry()
    forms = reg.setdefault("forms", {})
    entry = forms.setdefault(form_key, {"label": form_key, "status": "missing"})
    entry.update({"status": "proven", "exemplar": exemplar_filename,
                  "provenTake": proven_take, "provenBy": proven_by})
    if notes:
        entry["notes"] = notes
    REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return entry


def library_status():
    """One line per form — what's proven, what's still to be discovered."""
    reg = load_registry().get("forms", {})
    rows = []
    for key, e in reg.items():
        mark = "PROVEN " if e.get("status") == "proven" else "missing"
        detail = (f"{e.get('provenTake')} — {e.get('provenBy')}"
                  if e.get("status") == "proven" else e.get("appliesTo", ""))
        rows.append(f"  [{mark}] {key:<22} {detail}")
    proven = sum(1 for e in reg.values() if e.get("status") == "proven")
    return f"FORMULA LIBRARY — {proven}/{len(reg)} forms proven\n" + "\n".join(rows)


if __name__ == "__main__":
    print(library_status())
