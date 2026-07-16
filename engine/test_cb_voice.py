#!/usr/bin/env python3
"""test_cb_voice.py — regression coverage for cb_voice.py's ZERO-API-CALL logic.

cb_voice.py (the Voice Director) had NO test coverage before this file. This covers
_resolve_speaker — the pure, deterministic speaker-label-to-canonical-character resolver
that every voice path (build_dialogue_track, audit_attribution, the manual voiceScript
override) depends on. In particular it locks in the 2026-07-08 audit fix: EXACT match
must be tried across the whole candidate pool BEFORE any substring fallback, so a short
name (e.g. "Keen") can never silently resolve to a longer, unrelated name that happens to
contain it as a substring (e.g. "Keen's Mum") just because that longer name was checked
first in an unordered/positional pass.

Convention matches test_cb_qa.py / test_gate_cascade.py / test_unapprove_locks.py: plain
Python, assert-style checks recorded via check(), no pytest/unittest, a main() that prints
PASS/FAIL per case and sys.exit(1) on any failure. No network/API calls — _resolve_speaker
is pure (string/dict logic only), so this needs no stubbing of cb_gen/ElevenLabs.

    python3 test_cb_voice.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cb_voice

RESULTS = []  # (name, ok, detail)


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


# ═══════════════════════════════════════════════════════════════════════════════════
# _resolve_speaker — EXACT-MATCH PRECEDENCE (2026-07-08 audit fix, Law 5 risk)
#
# Before the fix, the resolver walked `list(pool) + _canon_names()` and returned the
# FIRST candidate for which `cl == ll or ll in cl or cl in ll` held — a single combined
# equality-or-substring test. Because "Keen's Mum" is checked as a substring candidate
# against the label "KEEN" (ll="keen" is a substring of cl="keen's mum"), and because
# Mum was listed FIRST in the beat's speaker pool, "KEEN" could resolve to "Keen's Mum"
# before the loop ever reached the real, exact "Keen" entry — misattributing Keen's own
# lines to his mother's voice. The fix: try an EXACT match across the WHOLE pool first;
# only fall back to substring matching when no exact name exists anywhere in the pool.
# ═══════════════════════════════════════════════════════════════════════════════════
def test_exact_match_precedence_keen_vs_mum():
    # Mum listed FIRST — this is what actually exercises the order-dependent bug: a
    # positional/first-match scan would hit "Keen's Mum" (a substring superset of "keen")
    # before ever reaching the real "Keen" entry later in the pool.
    shot = {"speakers": ["Keen's Mum", "Keen"]}

    resolved_keen = cb_voice._resolve_speaker("KEEN", shot)
    check("_resolve_speaker: 'KEEN' resolves to 'Keen' (never 'Keen's Mum') even when Mum is listed first",
          resolved_keen == "Keen", f"got {resolved_keen!r}")

    # Mirror case: a label that IS "Keen's Mum" must resolve to the full name, not get
    # truncated/short-circuited onto the shorter "Keen" entry it happens to contain.
    resolved_mum = cb_voice._resolve_speaker("KEEN'S MUM", shot)
    check("_resolve_speaker: 'KEEN'S MUM' resolves to 'Keen's Mum' (not truncated to 'Keen')",
          resolved_mum == "Keen's Mum", f"got {resolved_mum!r}")

    # Same pair, opposite pool order — the fix must not be order-dependent either way.
    shot_reordered = {"speakers": ["Keen", "Keen's Mum"]}
    resolved_keen2 = cb_voice._resolve_speaker("KEEN", shot_reordered)
    check("_resolve_speaker: 'KEEN' -> 'Keen' is stable regardless of pool order (Keen first)",
          resolved_keen2 == "Keen", f"got {resolved_keen2!r}")
    resolved_mum2 = cb_voice._resolve_speaker("KEEN'S MUM", shot_reordered)
    check("_resolve_speaker: 'KEEN'S MUM' -> 'Keen's Mum' is stable regardless of pool order",
          resolved_mum2 == "Keen's Mum", f"got {resolved_mum2!r}")


# ═══════════════════════════════════════════════════════════════════════════════════
# _resolve_speaker — SUBSTRING FALLBACK STILL FUNCTIONS
#
# The exact-match-first fix must not remove substring matching entirely — it's still the
# correct behaviour when no exact candidate exists anywhere in the pool (e.g. a script
# label using a shortened/informal form of a character's name).
# ═══════════════════════════════════════════════════════════════════════════════════
def test_substring_fallback_still_works():
    # "Fuzzby" is not in this beat's own speaker pool at all, so the resolver must widen
    # to the full canon pool (_canon_names()); "FUZZ" doesn't exact-match "Fuzzby", so
    # this only passes if the substring fallback still fires.
    shot = {"speakers": ["Zenny"]}
    resolved = cb_voice._resolve_speaker("FUZZ", shot)
    check("_resolve_speaker: substring fallback still resolves 'FUZZ' -> 'Fuzzby' when no exact match exists",
          resolved == "Fuzzby", f"got {resolved!r}")

    # A genuinely unresolvable label (not an exact OR substring match against anyone)
    # falls through to label.title() — confirming the fallback chain still terminates
    # sanely rather than raising.
    resolved_none = cb_voice._resolve_speaker("XYZQXYZQ", shot)
    check("_resolve_speaker: a wholly unmatched label falls back to label.title(), not a crash",
          resolved_none == "Xyzqxyzq", f"got {resolved_none!r}")


# ═══════════════════════════════════════════════════════════════════════════════════
# _resolve_speaker — UNLABELLED LINE (None) behaviour, the other half of the empty-pool
# gap audit_attribution/build_dialogue_track now guard against.
# ═══════════════════════════════════════════════════════════════════════════════════
def test_unlabelled_resolution():
    resolved = cb_voice._resolve_speaker(None, {"speakers": ["Zenny", "Fuzzby"]})
    check("_resolve_speaker: an unlabelled line resolves to the sole/first speaker in the pool",
          resolved == "Zenny", f"got {resolved!r}")

    resolved_empty = cb_voice._resolve_speaker(None, {"speakers": []})
    check("_resolve_speaker: an unlabelled line with an EMPTY pool resolves to None (never invents a speaker)",
          resolved_empty is None, f"got {resolved_empty!r}")


# ═══════════════════════════════════════════════════════════════════════════════════
# _is_wordless_held — THE SHARED, HARDENED wordlessHeld COERCION (2026-07-14, sweeping
# rule 61/70's fix to the two sibling call sites it never reached: _is_tender and
# audit_attribution both used bare truthiness on this SAME field, live on real production
# data as the JSON STRING "false" once already).
# ═══════════════════════════════════════════════════════════════════════════════════
def test_wordless_held_coercion():
    check("_is_wordless_held: real bool True -> True",
          cb_voice._is_wordless_held({"wordlessHeld": True}) is True)
    check("_is_wordless_held: real bool False -> False",
          cb_voice._is_wordless_held({"wordlessHeld": False}) is False)
    check("_is_wordless_held: the string 'false' (the real bug once found live) -> False, not truthy-True",
          cb_voice._is_wordless_held({"wordlessHeld": "false"}) is False)
    check("_is_wordless_held: the string 'true' (any case) -> True",
          cb_voice._is_wordless_held({"wordlessHeld": "TRUE"}) is True)
    check("_is_wordless_held: field missing entirely -> False",
          cb_voice._is_wordless_held({}) is False)
    check("_is_wordless_held: shot itself is None -> False, never raises",
          cb_voice._is_wordless_held(None) is False)
    # the two sibling call sites now delegate to the shared helper — prove each one
    # correctly stops treating a stray "false" string as wordless.
    check("_is_tender: a 'false'-string wordlessHeld does not force the tender palette on its own",
          cb_voice._is_tender({"wordlessHeld": "false", "emotionalIntent": ""}) is False)
    import json as _json, tempfile, os as _os
    tmp = tempfile.mkdtemp(prefix="cb_voice_test_")
    try:
        pkg = _os.path.join(tmp, "scratch.json")
        # A deliberately UNRESOLVABLE speaker label ("NOTAREALCHARACTER") on the one cut — if this
        # beat is correctly audited (not wrongly skipped as wordless), audit_attribution MUST report
        # a problem for it. An empty `problems` list here would mean the beat was silently skipped —
        # the exact old bug this test guards against, made observable by giving it something real to
        # actually catch (an empty-problems result on a CLEAN beat wouldn't distinguish "audited and
        # fine" from "skipped").
        _json.dump({"beats": [{"beatCode": "1.B1", "wordlessHeld": "false", "cuts": [
            {"n": 1, "dialogue": "NOTAREALCHARACTER: Hi.", "voiceTreatment": None}]}]}, open(pkg, "w"))
        problems = cb_voice.audit_attribution(pkg)
        check("audit_attribution: a 'false'-string wordlessHeld beat is still actually audited (not skipped) — "
              "proven by it correctly catching the deliberately-unresolvable speaker label",
              any("1.B1" in p for p in problems), problems)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════════════
# voiceScript GATED BEHIND EXPLICIT CONFIRMATION (2026-07-14, rules 82/83 — Julian: "keep
# them for genuine edge cases, but require an explicit confirmation... flag it visibly so
# it's never silent"). Before this fix, ANY non-empty voiceScript silently bypassed the
# whole directed cadence/tag compiler (Andrea Romano + Docter + Brumm's own "THE MIND") the
# instant it was present — now it's ignored (falls through to the real directed performance)
# unless the SAME beat also carries voiceScriptConfirmed: true.  Pure logic, zero API calls
# (direct_line() only touches phonetic/_tags/_leak — text/dict manipulation, no network).
# ═══════════════════════════════════════════════════════════════════════════════════
def test_voice_script_override_gated_behind_confirmation():
    base = {
        "beatCode": "1.B1",
        "speakers": ["Fuzzby"],
        "cuts": [{"n": 1, "dialogue": "FUZZBY: Nailed it.", "voiceTreatment": None, "delivery": ""}],
    }

    # Case 1 — voiceScript present but UNCONFIRMED: must be ignored entirely, falling
    # through to the real directed cadence/tag compiler (the actual cut dialogue is used).
    unconfirmed = dict(base, voiceScript="FUZZBY: [whispering] Some hand-typed override line.")
    turns_unconfirmed = cb_voice._resolve_turns(unconfirmed, {})
    check("_resolve_turns: an UNCONFIRMED voiceScript is ignored — no turn carries its override text",
          all("Some hand-typed override line" not in (t.get("text") or "") for t in turns_unconfirmed),
          turns_unconfirmed)
    check("_resolve_turns: an UNCONFIRMED voiceScript still produces the real directed turn from cuts[]",
          len(turns_unconfirmed) == 1 and turns_unconfirmed[0]["character"] == "Fuzzby",
          turns_unconfirmed)

    # Case 2 — voiceScript present AND confirmed: ships VERBATIM (pre=line, so direct_line's
    # own cadence/tag compiler never runs on it — matching the function's own "CONFIRMED
    # MANUAL OVERRIDE... used VERBATIM" contract).
    confirmed = dict(base, voiceScript="FUZZBY: [whispering] Some hand-typed override line.",
                     voiceScriptConfirmed=True)
    turns_confirmed = cb_voice._resolve_turns(confirmed, {})
    check("_resolve_turns: a CONFIRMED voiceScript ships its override text verbatim",
          len(turns_confirmed) == 1
          and turns_confirmed[0]["text"] == "[whispering] Some hand-typed override line.",
          turns_confirmed)
    check("_resolve_turns: a CONFIRMED voiceScript resolves the speaker label to the real character",
          turns_confirmed[0]["character"] == "Fuzzby", turns_confirmed)

    # Case 3 — no voiceScript at all: must match Case 1's real-turn shape exactly (proving
    # "unconfirmed" and "absent" are treated identically, never a half-applied bypass).
    absent = dict(base)
    turns_absent = cb_voice._resolve_turns(absent, {})
    check("_resolve_turns: no voiceScript at all produces the identical real turn as the unconfirmed case",
          [t["character"] for t in turns_absent] == [t["character"] for t in turns_unconfirmed]
          and turns_absent[0]["text"] == turns_unconfirmed[0]["text"],
          (turns_absent, turns_unconfirmed))


# ═══════════════════════════════════════════════════════════════════════════════════
# A deliberately-broken-assertion smoke test proving this harness can actually fail.
# Set BREAK_ME_FOR_REAL = True temporarily to confirm a real regression is caught, then
# revert to False before shipping (kept here, disabled, as documentation of that step).
# ═══════════════════════════════════════════════════════════════════════════════════
BREAK_ME_FOR_REAL = False


def main():
    if BREAK_ME_FOR_REAL:
        check("DELIBERATE BREAK (must show FAIL)", False, "proving the harness catches a real regression")

    test_exact_match_precedence_keen_vs_mum()
    test_substring_fallback_still_works()
    test_unlabelled_resolution()
    test_wordless_held_coercion()
    test_voice_script_override_gated_behind_confirmation()

    fails = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n        -> {detail}" if not ok and detail else ""))
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} passed.")
    if fails:
        print(f"{len(fails)} FAILURE(S)")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
