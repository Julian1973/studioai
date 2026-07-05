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


def current_snapshot():
    """{key: prompt text} for every golden-set entry, built the SAME way the live paths build them
    (cb_segprompt.shipped_prompt — the shared decision gate3_dryrun/cb_beats.run/get_seedance_prompt all call,
    v2 first with v1 as a loud logged fallback; cb_scene.keyframe_for for the keyframe) — never a bespoke
    re-implementation, and never a raw for_beat()/for_beat_v2() call that could measure a path nothing ships."""
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
        # segment must be the settle (labelled "settle:"), matching the Handle Doctrine's fixed split.
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
            if f"{CS.HANDLE_ACTION}-{CS.HANDLE_TOTAL}s settle:" not in body:
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
