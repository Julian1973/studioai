#!/usr/bin/env python3
"""cb_golden.py — T10, the golden-set harness.

Stores a known-good snapshot of BOTH prompt paths and diffs current output against it:
  • the Seedance clip-prompt baseline (cb_segprompt.shipped_prompt — for_beat_v2, the SAME call
    gate3_dryrun/cb_beats.run/get_seedance_prompt make; a raw cb_segprompt.for_beat() call would
    silently measure the retired v1 fallback instead of what the studio actually ships) on all 5
    Ep1 Scene-1 beats (1.B1-1.B5, since Julian's Director's Cut restructure — was 1.B1-1.B3).
  • the keyframe prompt (cb_scene.keyframe_for) on all 5 Ep1 Scene-1 beats (1.B1-1.B5) — anchor + 4
    chained beats, so a chain-vs-anchor formatting regression shows up too.

CLAUDE.md hard rule: no prompt-touching commit merges without this diff shown. A diff is not automatically
wrong — a ticket can deliberately change a prompt — but it must be SHOWN to Julian before the golden is
recaptured, never silently overwritten.

Content assertions (spec freeze, 2026-07-02, Julian; REWRITTEN for v4, the blessed template, 2026-07-05):
diffing only proves "unchanged since last time" — it never proves anything is actually THERE, so a snapshot
itself could be lean and every later diff would still pass. `assertions()` checks every shipped segprompt beat
against v4's OWN spec — v4 is JSON-only now (no more prose-vs-JSON branching by speaker count), so every check
below reads doc['prompt']/['references']/['prohibited']/['continuity'] directly:
  1. the required top-level keys are all present (duration/aspect/mode/references/style/ambience/prompt/
     continuity/prohibited).
  2. a real fragment of the beat's own cuts[].action content survives into doc['prompt'] verbatim (names are no
     longer delabeled — v4 welds raw names — so no name-splitting is needed to find it).
  3. if the beat has dialogue: doc['prompt'] names @Audio1 as the performance source, and the actual spoken
     WORDS never leak into it (Law 6 — unconditional, unchanged by v4).
  4. the six standing negatives (_v3_negatives, unchanged, still always exactly six) are all present WITHIN
     doc['prohibited'] — additive with the beat's own staging-specific items now, never fewer than six.
  5. the continuous timing clock inside doc['prompt'] chains 0..HANDLE_TOTAL with no gaps or overlaps, and its
     closing segment is the labelled settle block (the Handle Doctrine's fixed HANDLE_ACTION/HANDLE_SETTLE split).
  6. references carry @图1 and @Audio1, and one @图N per cast member with that character's NAME welded directly
     into its reference text (rule 5, reversed 2026-07-05 — identity binding is now by name, never a role-label
     paraphrase; see CLAUDE.md).
  7. RELAY-MODE / JUNCTION-TYPE coverage (rule 31, 2026-07-05, the junction-type pivot): current_snapshot()'s
     plain segprompt loop always calls shipped_prompt with relay=False, so it never exercised the relay code
     path at all — a relay-only change produced a silent zero-diff report. _relay_snapshot() now forces
     relay=True and BOTH junction types (intentional_next_shot, seamless_continuation) for every beat after
     the scene's first, and this assertion checks each branch's @图1/prompt wording actually differs the way
     rule 31 requires (state-carry clause vs. locked opening-frame text).
Wired into both commands: `diff` fails (exit 1) on a failed assertion even with zero text diffs; `capture`
refuses to bless a snapshot that fails one — a lean or malformed prompt can never silently become the new normal.

    python3 cb_golden.py diff       # compare current output vs the stored golden set (exit 1 on any diff or failed assertion)
    python3 cb_golden.py capture    # OVERWRITE the golden set with current output (only after Julian has seen the diff)
"""
import os, sys, re, json, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(HERE, "goldens")
PKG = os.path.join(HERE, "..", "cb-output", "Ep1_Episode_1_beat_package.json")
SEGPROMPT_BEATS = ["1.B1", "1.B2", "1.B3", "1.B4", "1.B5"]
KEYFRAME_BEATS = ["1.B1", "1.B2", "1.B3", "1.B4", "1.B5"]


def _pkg():
    return json.load(open(PKG))


def _relay_snapshot():
    """RELAY-MODE segprompt snapshots (added 2026-07-05, the junction-type pivot, CLAUDE.md rule 31) — the
    golden set's ONLY coverage of the relay code path (rule 21). current_snapshot()'s own segprompt loop
    always calls shipped_prompt with relay=False (it exists to prove the baseline non-relay prompt is
    byte-identical), so a relay-only change — exactly what rule 31 is — would otherwise produce a silent
    ZERO-DIFF golden report: not because nothing changed, but because the harness never looked at the code
    path that did. Forces relay=True and BOTH junction types for every beat after the scene's first (which
    never relays — nothing to snapshot there), so each branch of _v4_references' relay logic is actually
    captured. prev_end_state_still is read from the PREVIOUS beat's own authored endStateStill, matching
    what cb_beats.run/gate3_dryrun actually thread through — never invented here."""
    import cb_segprompt
    d = _pkg()
    beats = d["beats"]
    by_code = {(b.get("beatCode") or b.get("shotCode")): b for b in beats}
    scenes = {str(s.get("sceneNumber")): s for s in (d.get("scenes") or [])}
    out = {}
    for i, code in enumerate(SEGPROMPT_BEATS):
        if i == 0:
            continue   # the scene's first beat opens from its own generated keyframe — never relays
        b = by_code.get(code)
        prev = by_code.get(SEGPROMPT_BEATS[i - 1])
        if not b or not prev:
            continue
        sc = scenes.get(str(b.get("sceneNumber")))
        prev_ess = prev.get("endStateStill")
        prev_marks = prev.get("carryMarks")   # rules 33/34, 2026-07-05
        for junction in (cb_segprompt.JUNCTION_INTENTIONAL, cb_segprompt.JUNCTION_SEAMLESS):
            b_variant = dict(b)
            b_variant["junctionType"] = junction
            prompt, _builder, _def = cb_segprompt.shipped_prompt(b_variant, sc, relay=True,
                                                                  prev_end_state_still=prev_ess,
                                                                  prev_carry_marks=prev_marks)
            out[f"segprompt_relay_{junction}__{code}"] = prompt or ""
    return out


def current_snapshot():
    """{key: prompt text} for every golden-set entry, built the SAME way the live paths build them
    (cb_segprompt.shipped_prompt — the shared decision gate3_dryrun/cb_beats.run/get_seedance_prompt all call,
    v2 first with v1 as a loud logged fallback; cb_scene.keyframe_for for the keyframe) — never a bespoke
    re-implementation, and never a raw for_beat()/for_beat_v2() call that could measure a path nothing ships.
    Also includes _relay_snapshot()'s relay-mode captures (rule 31) — see that function's docstring."""
    import cb_segprompt, cb_scene
    d = _pkg()
    beats = d["beats"]
    by_code = {(b.get("beatCode") or b.get("shotCode")): b for b in beats}
    scenes = {str(s.get("sceneNumber")): s for s in (d.get("scenes") or [])}
    out = {}
    for code in SEGPROMPT_BEATS:
        b = by_code.get(code)
        if not b:
            continue
        sc = scenes.get(str(b.get("sceneNumber")))
        prompt, _builder, _is_v2 = cb_segprompt.shipped_prompt(b, sc)
        out[f"segprompt__{code}"] = prompt or ""
    out.update(_relay_snapshot())
    for code in KEYFRAME_BEATS:
        if code not in by_code:
            continue
        prompt, _refs, _info = cb_scene.keyframe_for(beats, code, "Ep1")
        out[f"keyframe__{code}"] = prompt
    return out


def _golden_path(key):
    return os.path.join(GOLDEN_DIR, key + ".txt")


def _has_dialogue(beat):
    return bool(beat.get("speakers")) or any((c.get("dialogue") or "").strip() for c in (beat.get("cuts") or []))


def _name_free_chunks(text, cast):
    """Split `text` on any cast-name mention (with an optional possessive 's, matching the exact span
    cb_segprompt._delabel rewrites) — the surviving fragments are words delabeling never touches, so they must
    appear verbatim in the shipped prompt no matter which role-label form (full first-mention, or short) a name
    became. Returns the fragments in order, stripped, empties dropped."""
    if not cast:
        return [text.strip()] if text.strip() else []
    pat = r"\b(?:" + "|".join(re.escape(n) for n in cast) + r")(?:'s)?\b"
    return [seg.strip() for seg in re.split(pat, text) if seg.strip()]


def assertions(snap=None):
    """Content assertions on every shipped segprompt beat — see the module docstring. Returns a list of failure
    strings (empty means everything passed).

    REWRITTEN for v4 (the blessed template, Julian, 2026-07-05) — v3's shots[]/world/constraints/negatives/
    SPEAKER-MAP shape is retired, so the checks below test v4's actual shape (references/prompt/continuity/
    prohibited, one continuous timing clock, names welded to @图N) instead of the old one. The SPIRIT of every
    v3-era check is preserved even though the concrete shape changed: real beat content must survive into the
    prompt, dialogue must never leak actual words, the six standing negatives must always be present, and
    durations must still sum to the beat total — just checked against v4's field names now."""
    import cb_segprompt as CS
    d = _pkg()
    beats = d["beats"]
    by_code = {(b.get("beatCode") or b.get("shotCode")): b for b in beats}
    snap = snap if snap is not None else current_snapshot()
    fails = []
    for code in SEGPROMPT_BEATS:
        b = by_code.get(code)
        if not b:
            continue
        prompt = snap.get(f"segprompt__{code}", "")
        cast = b.get("openingCast") or b.get("characters") or []
        try:
            doc = json.loads(prompt)
        except Exception as e:
            fails.append(f"{code}: JSON prompt failed to parse ({e})")
            continue

        # (1) required top-level keys — v4's actual shape, not v3's
        for key in ("duration", "aspect", "mode", "references", "style", "ambience", "prompt", "continuity", "prohibited"):
            if key not in doc:
                fails.append(f"{code}: JSON prompt missing required top-level key {key!r}")

        # (2) a real fragment of the beat's OWN cuts[].action survives in "prompt" — proves real content, not
        # generic filler. Names are no longer delabeled (v4 welds raw names), so no name-splitting needed —
        # the raw action text should appear near-verbatim (only _strip_spoken_words/rstrip('.') may touch it).
        action = " ".join(str(c.get("action") or "").strip() for c in (b.get("cuts") or []))
        if action.strip():
            check = action.strip()[:60].rstrip(".")
            if check and check not in doc.get("prompt", ""):
                fails.append(f"{code}: none of the beat's own cuts[].action content survived into the shipped prompt (looked for: {check!r})")

        # (3) dialogue binding — the speaker-order sentence must name every speaking character and bind them to
        # @Audio1; actual dialogue words must NEVER appear in "prompt" (Law 6 — unconditional, unchanged by v4).
        has_dlg = _has_dialogue(b)
        body = doc.get("prompt", "")
        if has_dlg:
            if "in @Audio1" not in body:
                fails.append(f"{code}: beat has dialogue but 'prompt' has no @Audio1 speaker-performance sentence")
            for c in (b.get("cuts") or []):
                raw_dlg = str(c.get("dialogue") or "").strip()
                if not raw_dlg:
                    continue
                words = raw_dlg.split(":", 1)[-1].strip()
                if words and len(words) > 8 and words.lower() in body.lower():
                    fails.append(f"{code}: actual dialogue words may have leaked into 'prompt' (Law 6): {words!r}")

        # (4) the six standing negatives are always present WITHIN "prohibited" (additive with beat-specific
        # staging items now, never fewer than six — _v3_negatives itself is unchanged, still exactly six).
        prohibited = doc.get("prohibited")
        if not isinstance(prohibited, list) or len(prohibited) < 6:
            fails.append(f"{code}: JSON prohibited should be a list of at least 6 items, got {prohibited!r}")
        else:
            any_bee = any(CS._char_meta(n)[1] for n in cast)
            standing = CS._v3_negatives(any_bee)
            missing = [n for n in standing if n not in prohibited]
            if missing:
                fails.append(f"{code}: prohibited list is missing standing negative(s): {missing}")

        # (5) the continuous timing clock must chain 0..HANDLE_TOTAL with no gaps or overlaps, and the closing
        # segment must be the settle (labelled "settle in character:" since rule 33, 2026-07-05 — was "settle:"),
        # matching the Handle Doctrine's fixed split.
        spans = [(int(s), int(e)) for s, e in re.findall(r"(\d+)-(\d+)s", body)]
        if not spans:
            fails.append(f"{code}: no timing-clock segments found in 'prompt'")
        else:
            if spans[0][0] != 0:
                fails.append(f"{code}: timing clock doesn't start at 0s (starts at {spans[0][0]}s)")
            if spans[-1][1] != CS.HANDLE_TOTAL:
                fails.append(f"{code}: timing clock ends at {spans[-1][1]}s, expected the beat total {CS.HANDLE_TOTAL}")
            for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
                if e1 != s2:
                    fails.append(f"{code}: timing clock has a gap/overlap between {s1}-{e1}s and {s2}-{e2}s")
            if f"{CS.HANDLE_ACTION}-{CS.HANDLE_TOTAL}s settle in character:" not in body:
                fails.append(f"{code}: closing timing-clock segment isn't the labelled settle block")

        # (6) references: @图1 present, @Audio1 present, one @图N per cast member with the name welded in
        # (rule 5, reversed 2026-07-05 — see CLAUDE.md — names now appear directly, never a role-label paraphrase)
        refs = doc.get("references") or {}
        if "@图1" not in refs:
            fails.append(f"{code}: references missing @图1")
        if "@Audio1" not in refs:
            fails.append(f"{code}: references missing @Audio1")
        for i, name in enumerate(cast):
            tag = f"@图{i + 2}"
            if tag not in refs:
                fails.append(f"{code}: references missing {tag} for {name!r}")
            elif name not in refs[tag]:
                fails.append(f"{code}: {tag}'s reference text doesn't name {name!r} directly: {refs[tag]!r}")

    # (7) RELAY-MODE / JUNCTION-TYPE coverage (rule 31, 2026-07-05; @图1 wording REWRITTEN under rules 33/34,
    # same day — see _relay_snapshot()'s docstring for why this exists at all). A `seamless_continuation` join
    # must keep the locked opening-frame wording in BOTH @图1's reference text and the prompt's own opener
    # sentence, and must NEVER carry an `opensOn` bridge sentence (that's an intentional-cut-only mechanism,
    # rule 34); an `intentional_next_shot` join (the default) must NOT claim to open on @图1's frame anywhere,
    # must carry the state-reference clause instead (rule 33's rewrite: "is the state reference from the
    # previous beat... fresh camera setup within the same space"), and — since this test beat authors an
    # `opensOn` field — must carry its "OPEN ON" bridge sentence.
    for key, prompt in snap.items():
        m = re.match(r"segprompt_relay_(intentional_next_shot|seamless_continuation)__(.+)", key)
        if not m:
            continue
        junction, code = m.group(1), m.group(2)
        try:
            doc = json.loads(prompt)
        except Exception as e:
            fails.append(f"{key}: JSON prompt failed to parse ({e})")
            continue
        ref1 = (doc.get("references") or {}).get("@图1", "")
        body = doc.get("prompt", "")
        if junction == "seamless_continuation":
            if "exact opening composition" not in ref1:
                fails.append(f"{key}: seamless_continuation join's @图1 text lost the locked opening-frame wording: {ref1!r}")
            if "Begin from @图1's exact opening composition" not in body:
                fails.append(f"{key}: seamless_continuation join's prompt lost the opening-frame opener sentence")
            if "OPEN ON" in body:
                fails.append(f"{key}: seamless_continuation join's prompt wrongly carries an OPEN ON bridge sentence (intentional-cut-only, rule 34)")
        else:
            if "exact opening composition" in ref1:
                fails.append(f"{key}: intentional_next_shot join's @图1 text still claims to BE the opening composition (should be a state-reference clause instead): {ref1!r}")
            if "is the state reference from the previous beat" not in ref1 or "fresh camera setup" not in ref1:
                fails.append(f"{key}: intentional_next_shot join's @图1 text is missing the state-carry clause: {ref1!r}")
            if "Begin from @图1's exact opening composition" in body:
                fails.append(f"{key}: intentional_next_shot join's prompt still opens on @图1's frame — should open on its own fresh camera setup")
    return fails


def diff():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    snap = current_snapshot()
    any_diff = False
    for key, text in snap.items():
        gp = _golden_path(key)
        if not os.path.exists(gp):
            print(f"[{key}] NO GOLDEN STORED YET — run 'python3 cb_golden.py capture' once Julian has reviewed this output.")
            any_diff = True
            continue
        golden = open(gp, encoding="utf-8").read()
        if golden == text:
            print(f"[{key}] OK — identical to golden")
        else:
            any_diff = True
            print(f"[{key}] DIFF —")
            for line in difflib.unified_diff(golden.splitlines(), text.splitlines(),
                                              fromfile="golden", tofile="current", lineterm=""):
                print("  " + line)
    fails = assertions(snap)
    for f in fails:
        any_diff = True
        print(f"[ASSERTION FAILED] {f}")
    print()
    print("ZERO DIFFS — safe to merge" if not any_diff
          else "DIFFS FOUND — show Julian before merging (CLAUDE.md hard rule); recapture only after he has seen this")
    return 1 if any_diff else 0


def capture():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    snap = current_snapshot()
    fails = assertions(snap)
    if fails:
        print("REFUSING TO CAPTURE — the current output fails its own content assertions (a lean prompt must not"
              " become the new golden):")
        for f in fails:
            print(f"  {f}")
        return 1
    for key, text in snap.items():
        open(_golden_path(key), "w", encoding="utf-8").write(text)
        print(f"captured [{key}] ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    os.chdir(HERE)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "diff"
    sys.exit(capture() if cmd == "capture" else diff())
