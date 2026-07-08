#!/usr/bin/env python3
"""cb_golden.py — T10, the golden-set harness.

Stores a known-good snapshot of BOTH prompt paths and diffs current output against it:
  • the Seedance clip-prompt baseline (cb_segprompt.shipped_prompt — v5 under GATE3_ANIMATION_DOCTRINE.md,
    the Version of Record as of 2026-07-06 — the SAME call gate3_dryrun/cb_beats.run/get_seedance_prompt make)
    on all 5 Ep1 Scene-1 beats (1.B1-1.B5).
  • the keyframe prompt (cb_scene.keyframe_for) on all 5 Ep1 Scene-1 beats (1.B1-1.B5) — anchor + 4 chained
    beats, so a chain-vs-anchor formatting regression shows up too.

CLAUDE.md hard rule: no prompt-touching commit merges without this diff shown. A diff is not automatically
wrong — a ticket can deliberately change a prompt — but it must be SHOWN to Julian before the golden is
recaptured, never silently overwritten. NOT YET RECAPTURED for v5 as of this file's rewrite — golden
recapture waits on Julian's explicit approval of the zero-cost dry-run prompts, every time the shape changes.

Content assertions (REWRITTEN 2026-07-07, front-to-back audit — this numbered list had drifted from the
actual `_check_segprompt_body` code across two earlier revisions; corrected here to match the code exactly,
not the other way around, per rule 7; the tech-line CLOSER named below was itself retired 2026-07-08, rule
54 — fps folded into the HEADER): v5 is a PLAIN-TEXT document — HEADER, style, references, actingDNA,
beat story, and a Negative line (the camera/ambience paragraph named in earlier revisions of
this docstring was retired 2026-07-06, the thunder-leak bug — no such block exists in the current shape) —
not v4's JSON envelope. Every assertion below reads the raw compiled string, never json.loads.
`assertions()` checks every shipped segprompt beat:
  1. word budget — the hard cap (whole document, cb_preflight.WORD_BUDGET_BLOCK — 650 as of 2026-07-07,
     rule 52) is never exceeded.
  2. HEADER — `cb_segprompt._v5_header()` (now including fps, rule 54) opens the prompt.
  3. style law block — the show's STYLE_LAW text appears verbatim.
  4. references block — @图1 and @Audio1 both present; every ACTIVE cast member (named in this beat's own
     cuts/speakers/opensOn — cb_segprompt._v5_active_cast) gets its own name-welded "@图N Name — match
     exactly" line (doctrine §4a/4b's exact wording, no species/role label); a BACKGROUND cast member (THE
     CAST-SIZE FIX, 2026-07-07) is only required to have its own @图N tag present somewhere, consolidated
     into a shared line rather than repeating the full sentence.
  5. actingDNA block — every ACTIVE cast member's own actingNote (Fuzzby/Zenny) or bible.mannerisms (the 9
     bears) text appears VERBATIM — THE FIDELITY LAW: no separate authored field, the character's real store
     is the only source. A BACKGROUND cast member has no Acting DNA line in this beat's prompt at all by
     design — not checked, since nothing is there to check.
  6. beat story block — a real fragment of the beat's own FIRST CUT's action text survives (Block 4 has
     walked the beat's own cuts[] + endState since the shot-list ruling, never the retired flattened
     `storyBeat` summary field — speed adjectives and spoken words are stripped before the check, matching
     what the emitter itself strips); dialogue WORDS never leak (Law 6 — unconditional).
  7. Negative line — the eleven standing negatives (doctrine §2) plus the beat's own stagingProhibited are
     all present, terse, in the Negative line; `bible.dos`/`bible.donts` do NOT appear anywhere (doctrine
     §3 — "Never in a prompt... dos/donts live at Gate 1"). No separate tech-line check — retired, rule 54.
  8. RELAY coverage — current_snapshot()'s plain segprompt loop always calls shipped_prompt with relay=False,
     so it never exercises the relay code path at all; a relay-only change would otherwise produce a silent
     zero-diff report. _relay_snapshot() forces relay=True for every beat after the scene's first and this
     assertion checks the relay @图1 wording actually differs from the opener's (@Video1 retired 2026-07-07 —
     see cb_segprompt.py's module docstring, "THE FIFTH ANCHOR, RETIRED").
Wired into both commands: `diff` fails (exit 1) on a failed assertion even with zero text diffs; `capture`
refuses to bless a snapshot that fails one — a lean or malformed prompt can never silently become the new normal.

    python3 cb_golden.py diff       # compare current output vs the stored golden set (exit 1 on any diff or failed assertion)
    python3 cb_golden.py capture    # OVERWRITE the golden set with current output (only after Julian has seen the diff)
"""
import os, sys, re, json, glob, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(HERE, "goldens")
SEGPROMPT_BEATS = ["1.B1", "1.B2", "1.B3", "1.B4", "1.B5"]
KEYFRAME_BEATS = ["1.B1", "1.B2", "1.B3", "1.B4", "1.B5"]


class GoldenDormant(Exception):
    """Raised when no beat package exists to check against — the golden harness has nothing to compare,
    which is a legitimate state (a full reset, or before Stage 1 has ever produced a package), never a
    crash. `diff()`/`capture()` catch this at the top level and report cleanly instead."""
    pass


def _resolve_pkg_path():
    """Resolves the current production's beat package the SAME way cb_pipeline._resolve_pkg does — glob,
    newest by mtime, never a hardcoded filename or episode — so the golden harness re-arms automatically
    the moment a new package lands, whatever episode it's for. Returns None (never raises) when nothing
    exists yet; callers that need a package call _pkg(), which turns None into GoldenDormant."""
    cands = glob.glob(os.path.join(HERE, "..", "cb-output", "*beat_package.json"))
    if not cands:
        cands = glob.glob(os.path.join(HERE, "..", "cb-output", "*shot_package.json"))
    return max(cands, key=os.path.getmtime) if cands else None


def _pkg():
    p = _resolve_pkg_path()
    if not p:
        raise GoldenDormant()
    return json.load(open(p))


def _relay_snapshot():
    """RELAY-MODE segprompt snapshots — the golden set's ONLY coverage of the relay code path.
    current_snapshot()'s own segprompt loop always calls shipped_prompt with relay=False (it exists to prove
    the baseline opener prompt is byte-identical), so a relay-only change would otherwise produce a silent
    ZERO-DIFF golden report. One snapshot per beat after the scene's first (GATE3_ANIMATION_DOCTRINE.md gives
    every relay beat the SAME @图1 wording regardless of junctionType, so there is no second "junction type"
    variant left to capture, unlike the pre-doctrine harness; @Video1 retired 2026-07-07)."""
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
        if not b:
            continue
        sc = scenes.get(str(b.get("sceneNumber")))
        prompt, _builder, _def = cb_segprompt.shipped_prompt(b, sc, relay=True)
        out[f"segprompt_relay__{code}"] = prompt or ""
    return out


def current_snapshot():
    """{key: prompt text} for every golden-set entry, built the SAME way the live paths build them
    (cb_segprompt.shipped_prompt — the shared decision gate3_dryrun/cb_beats.run/get_seedance_prompt all
    call; cb_scene.keyframe_for for the keyframe) — never a bespoke re-implementation. Also includes
    _relay_snapshot()'s relay-mode captures — see that function's docstring."""
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
        prompt, _builder, _is_def = cb_segprompt.shipped_prompt(b, sc)
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


def _check_segprompt_body(code, body, beat, cast, fails):
    """Shared checks for both the plain opener snapshot and the relay snapshot of a beat — factored out so
    (8)/(9) below don't duplicate the whole per-beat block twice."""
    import cb_segprompt as CS
    if not body.strip():
        fails.append(f"{code}: shipped prompt is empty")
        return

    # (1) word budget — never over the hard cap (RAISED 2026-07-07, rule 52, from 400 to 650: the old cap
    # predated the shot-list restoration and decision 1's anti-hold-safe relay wording, both real content).
    import cb_preflight as PF
    wc = CS._v5_word_count(body)
    if wc > PF.WORD_BUDGET_BLOCK:
        fails.append(f"{code}: {wc} words — exceeds the {PF.WORD_BUDGET_BLOCK}-word hard cap, must not be captured as golden")

    # (2) HEADER opens the prompt — now carries fps too (rule 54, 2026-07-08: the standalone tech line
    # that used to state fps separately is retired).
    header = CS._v5_header()
    if not body.startswith(header):
        fails.append(f"{code}: prompt does not open with the doctrine's HEADER ({header!r})")

    # (3) style law block — verbatim.
    if CS._style() not in body:
        fails.append(f"{code}: style law text is missing from the shipped prompt")

    # (4) references block — @图1 and @Audio1 present; one @图N per cast member, name-welded, "match
    # exactly" for an ACTIVE cast member, or grouped into the consolidated background-cast line otherwise
    # (THE CAST-SIZE FIX, 2026-07-07 — cb_segprompt._v5_active_cast).
    if "@图1" not in body:
        fails.append(f"{code}: references block missing @图1")
    if "@Audio1" not in body:
        fails.append(f"{code}: references block missing @Audio1")
    active, _background = CS._v5_active_cast(beat, cast)
    for i, name in enumerate(cast):
        tag = f"@图{i + 2}"
        if name in active:
            if f"{tag} {name} — match exactly." not in body:
                fails.append(f"{code}: references block missing {tag!r}'s exact binding line for {name!r}")
        elif tag not in body:
            fails.append(f"{code}: references block missing {tag!r} entirely for background cast member {name!r}")

    # (5) actingDNA block — every ACTIVE cast member's own actingNote (or bible.mannerisms fallback) survives
    # verbatim; a BACKGROUND cast member has no Acting DNA line in this beat's prompt at all by design.
    for name in active:
        text, _field = CS._v5_acting_dna_source(name)
        if text and text not in body:
            fails.append(f"{code}: {name!r}'s {_field} text did not survive verbatim into the shipped prompt")

    # (6) beat story block — a real fragment of the beat's own shot list survives (FIXED 2026-07-07: Block 4
    # has walked the beat's own cuts[] + endState since the shot-list ruling, cb_segprompt._v5_beat_story's
    # own docstring — the flattened `storyBeat` summary field hasn't fed this block for a long time; checking
    # for it was failing on every single beat, a stale assertion, not a real regression guard); dialogue
    # WORDS never leak (Law 6).
    cuts = beat.get("cuts") or []
    if cuts:
        first_action = str(cuts[0].get("action") or "").strip()
        anchor = CS._v5_strip_speed_adjectives(CS._strip_spoken_words(first_action))[:40].rstrip()
        if anchor and anchor not in body:
            fails.append(f"{code}: none of the beat's own first-cut action survived into the shipped prompt (looked for: {anchor!r})")
    if _has_dialogue(beat):
        for c in (beat.get("cuts") or []):
            raw_dlg = str(c.get("dialogue") or "").strip()
            if not raw_dlg:
                continue
            words = raw_dlg.split(":", 1)[-1].strip()
            if words and len(words) > 8 and words.lower() in body.lower():
                fails.append(f"{code}: actual dialogue words may have leaked into the shipped prompt (Law 6): {words!r}")

    # (7) REMOVED 2026-07-07: the camera/ambience paragraph was retired 2026-07-06 (the thunder-leak bug,
    # cb_segprompt.py's own docstring) — scene.ambientBed no longer appears in the shipped prompt at all, so
    # asserting it must survive "verbatim" was failing unconditionally on every beat once every scene had an
    # ambientBed authored (this session's manifest-authoring pass). Ambience continuity is a Post/stitch
    # concern now (GATE3_ANIMATION_DOCTRINE.md Stage 7), not a shipped-prompt content assertion.

    # (8) HEADER + Negative line — RETIRED 2026-07-08 (rule 54): the standalone tech line is gone (fps
    # folded into the HEADER instead), so there is no separate tech-line survives-verbatim check anymore.
    if CS._v5_header() not in body:
        fails.append(f"{code}: the doctrine's HEADER line is missing or stale")
    for neg in CS._standing_negatives():
        if neg not in body:
            fails.append(f"{code}: Negative line is missing standing item {neg!r}")
    for name in cast:
        bible = ((CS._CHARS.get(name) or {}).get("bible") or {})
        for dos_item in (bible.get("dos") or [])[:1]:
            if str(dos_item).strip().rstrip(".") and str(dos_item).strip().rstrip(".") in body:
                fails.append(f"{code}: {name!r}'s bible.dos leaked into the shipped prompt — doctrine §3 bans it (Gate-1-only review criteria)")
        for donts_item in (bible.get("donts") or [])[:1]:
            if str(donts_item).strip().rstrip(".") and str(donts_item).strip().rstrip(".") in body:
                fails.append(f"{code}: {name!r}'s bible.donts leaked into the shipped prompt — doctrine §3 bans it (Gate-1-only review criteria)")


def assertions(snap=None):
    """Content assertions on every shipped segprompt beat — see the module docstring. Returns a list of
    failure strings (empty means everything passed)."""
    import cb_segprompt as CS
    d = _pkg()
    beats = d["beats"]
    by_code = {(b.get("beatCode") or b.get("shotCode")): b for b in beats}
    scenes = {str(s.get("sceneNumber")): s for s in (d.get("scenes") or [])}
    snap = snap if snap is not None else current_snapshot()
    fails = []

    for code in SEGPROMPT_BEATS:
        b = by_code.get(code)
        if not b:
            continue
        cast = b.get("openingCast") or b.get("characters") or []
        sc = scenes.get(str(b.get("sceneNumber")))
        b_with_scene = dict(b); b_with_scene["_scene_for_check"] = sc

        body = snap.get(f"segprompt__{code}", "")
        _check_segprompt_body(code, body, b_with_scene, cast, fails)
        if body.strip():
            # opener-specific: @图1 must be the doctrine's exact opener wording.
            if "@图1 opening keyframe — begin on this exact composition." not in body:
                fails.append(f"{code}: opener's @图1 line doesn't match the doctrine's exact wording")
            # @Video1 RETIRED (Julian, 2026-07-07 — "the video I don't like it either, I think it confuses
            # things"): must never appear anywhere, opener or relay.
            if "@Video1" in body:
                fails.append(f"{code}: @Video1 must never appear — retired 2026-07-07")

        # shot-list block must actually re-derive (Julian's 2026-07-06 ruling retired the old 80-word
        # sub-fence on this block — a real per-cut shot list needs room for camera + action per cut; the
        # whole-prompt hard cap (cb_preflight.WORD_BUDGET_BLOCK), checked separately, is the real backstop now).
        try:
            CS._v5_beat_story(b, cast)
        except Exception as e:
            fails.append(f"{code}: could not re-derive the shot-list block ({e})")

        # RELAY coverage (9) — the relay snapshot for this same beat (if it relays) must differ from the
        # opener wording and use the doctrine's exact fixed relay sentence.
        rkey = f"segprompt_relay__{code}"
        if rkey in snap:
            rbody = snap[rkey]
            _check_segprompt_body(rkey, rbody, b_with_scene, cast, fails)
            if rbody.strip():
                # THE ANTI-HOLD-SAFE RELAY WORDING (2026-07-07, decision 1) — supersedes the earlier "start
                # from this frame" sentence; see cb_segprompt._v5_references's docstring for the full ruling.
                if ("@图1 is the approved final frame of the previous beat and must be matched exactly as the "
                        "first frame only.") not in rbody:
                    fails.append(f"{rkey}: relay @图1 doesn't match the doctrine's exact state-reference wording")
                if "Do not hold the previous pose" not in rbody:
                    fails.append(f"{rkey}: relay @图1 is missing the anti-hold counter-instruction")
                if "@图1 opening keyframe — begin on this exact composition." in rbody:
                    fails.append(f"{rkey}: relay prompt wrongly carries the opener's @图1 wording")
                if "@Video1" in rbody:
                    fails.append(f"{rkey}: @Video1 must never appear — retired 2026-07-07")

    return fails


def diff():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    try:
        snap = current_snapshot()
    except GoldenDormant:
        print("no production loaded — golden set dormant (no beat package found in cb-output/); "
              "will re-arm automatically once a new package lands")
        return 0
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
    try:
        snap = current_snapshot()
    except GoldenDormant:
        print("no production loaded — golden set dormant (no beat package found in cb-output/); "
              "nothing to capture until a new package lands")
        return 0
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
