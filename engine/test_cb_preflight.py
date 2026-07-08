#!/usr/bin/env python3
"""test_cb_preflight.py — real, standalone regression tests for cb_preflight.py, THE MANIFEST gate
(CLAUDE.md rule 37/MANIFEST.md) — the choke-point every gate-arming call site (cb_pipeline.approve,
cb_beats.fire_next_beat, cb_replicator.walk_scene, cb-studio/serve.py) calls before proceeding.

This module had ZERO test coverage before this file. Matches the existing convention (test_gate_cascade.py,
test_unapprove_locks.py): plain Python, assert-driven, no pytest/unittest, a main() that runs every check and
prints PASS/FAIL, sys.exit(1) on any failure. Uses purely SCRATCH/synthetic beat+scene dicts constructed here
— never the real production package — so this never depends on live-state drift (the real package's own
manifest status changes week to week; this test's assertions must not).

    python3 test_cb_preflight.py
"""
import os, sys, json, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cb_preflight as PF


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# Scratch fixtures — a fully-compliant beat/scene pair, matching every field BOTH contracts require (per the
# real cb_preflight.py source: check_beat_technical / check_beat_creative / check_scene_technical /
# check_scene_creative). Deliberately synthetic content — these assertions are about GATE BEHAVIOUR, never
# about whether the prose itself is good.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _clean_beat(code, scene_num, is_opener=True, characters=None, opening_cast=None):
    b = {
        "beatCode": code, "sceneNumber": scene_num,
        "storyBeat": "Scratch story beat prose — not real content.",
        "endState": "scratch endState — not real content",
        "endStateStill": "scratch endStateStill — not real content",
        "carryMarks": "the scratch marker",
        "pauseHold": "one hold only: under 1 second",
        "actingContrast": "scratch acting contrast",
        "humourLayer": 2,
        "kidRead": "scratch kid read",
        "adultRead": "scratch adult read",
        "want": "scratch want",
        "need": "scratch need",
        "emotionMechanic": "scratch emotion-as-mechanic statement",
        "fidelityAllocation": {"primary": "Fuzzby", "secondary": "none", "economized": "none"},
        "pillar": "heart",
        "comedyMode": "BIG",
        "characters": characters if characters is not None else ["Fuzzby"],
        "openingCast": opening_cast if opening_cast is not None else [],
        "cuts": [{"n": 1, "framing": "wide", "action": "Fuzzby zips past."}],
    }
    if not is_opener:
        b["junctionType"] = "intentional_next_shot"
        b["opensOn"] = {"who": "Fuzzby", "action": "already mid-loop"}
    return b


def _clean_scene(scene_num=1):
    return {
        "sceneNumber": scene_num,
        "ambientBed": "scratch ambient bed — not real content",
        "parentLine": "scratch parent-layer line — not real content",
        "sceneLook": "scratch scene-look line — not real content",
        "pillar": "heart",
    }


def _pkg(tmp, beats, scenes):
    path = os.path.join(tmp, "Ep9_Scratch_beat_package.json")
    json.dump({"beats": beats, "scenes": scenes}, open(path, "w"))
    return path


def _sync_scratch_scene_cache(episode, scene_num, scene_dict):
    """Same fixture-helper convention as test_gate_cascade.py's own _sync_scratch_scene_cache: without a
    matching config/locations.json entry, cb_prompts.scene_cache_stale() correctly BLOCKs any scratch
    episode/scene as never-synced — real, working behaviour, but a different concern from what THIS test
    file is actually verifying. Injects a matching synced cache entry so scene-technical checks isolate the
    fields this test cares about, not scene-cache sync (a separate, already-covered check)."""
    import cb_prompts
    cb_prompts.LOCATIONS.setdefault(episode, {})[str(scene_num)] = {
        "_sourceHash": cb_prompts._scene_source_hash(scene_dict)
    }


class _Silent:
    """Swallow cb_preflight.run()'s log() prints (e.g. 'no script file found') so test output stays a clean
    PASS/FAIL list — those log lines are expected, informational noise for a scratch package with no real
    script/characters.json entries, not something this test needs to see."""
    def __call__(self, *a, **k):
        pass


def _run(tmp, pkg_path, episode="Ep9", scene_filter=None):
    return PF.run(pkg_path, episode=episode, scene_filter=scene_filter, gate="1", log=_Silent())


def _blocks(gaps, code=None, field=None):
    out = [g for g in gaps if g.kind == "BLOCK"]
    if code is not None:
        out = [g for g in out if g.code == code]
    if field is not None:
        out = [g for g in out if g.field == field]
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# 1. A fully-compliant beat/scene passes clean (no BLOCK on the beat's own manifest fields).
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_clean_beat_passes(tmp):
    fails = []
    beat = _clean_beat("9.B1", 9, is_opener=True)
    scene = _clean_scene(9)
    pkg = _pkg(tmp, [beat], [scene])
    _sync_scratch_scene_cache("Ep9", 9, scene)
    gaps, all_beats, scenes = _run(tmp, pkg)

    beat_blocks = _blocks(gaps, code="9.B1")
    if beat_blocks:
        fails.append(f"clean beat should have zero BLOCKs, got: {[ (g.field, g.detail) for g in beat_blocks ]}")

    ok, n, _ = PF.manifest_ok(pkg, scene="9", episode="Ep9")
    if not ok or n != 0:
        fails.append(f"manifest_ok should read (True, 0, ...) for a clean scratch scene, got ({ok}, {n})")
    return fails


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# 2. A beat missing a required TECHNICAL field (carryMarks) is caught as a named BLOCK.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_missing_technical_field_caught(tmp):
    fails = []
    beat = _clean_beat("9.B1", 9, is_opener=True)
    del beat["carryMarks"]
    scene = _clean_scene(9)
    pkg = _pkg(tmp, [beat], [scene])
    _sync_scratch_scene_cache("Ep9", 9, scene)
    gaps, _, _ = _run(tmp, pkg)

    hits = _blocks(gaps, code="9.B1", field="carryMarks")
    if not hits:
        fails.append("a beat with NO carryMarks key at all should raise a named carryMarks BLOCK, found none")

    ok, n, _ = PF.manifest_ok(pkg, scene="9", episode="Ep9")
    if ok:
        fails.append("manifest_ok should read False when carryMarks is missing")
    return fails


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# 3. A beat with a BLANK (not missing) required CREATIVE field is caught — proves _blank()'s
#    "present but empty string" path, distinct from a genuinely absent key.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_blank_creative_field_caught(tmp):
    fails = []
    beat = _clean_beat("9.B1", 9, is_opener=True)
    beat["kidRead"] = "   "   # present, non-None, but blank after strip() — the exact case _blank() exists for
    scene = _clean_scene(9)
    pkg = _pkg(tmp, [beat], [scene])
    _sync_scratch_scene_cache("Ep9", 9, scene)
    gaps, _, _ = _run(tmp, pkg)

    hits = _blocks(gaps, code="9.B1", field="kidRead")
    if not hits:
        fails.append("a beat with kidRead='   ' (blank, not missing) should still raise a kidRead BLOCK, found none")

    # sanity: the KEY is present (proves this is testing the blank-string path, not accidentally the missing-key path)
    if "kidRead" not in beat:
        fails.append("test setup error: kidRead key must be present (blank) for this to test the right path")
    return fails


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# 4. REGRESSION: check_beat_word_count must derive relay status via cb_scene.relay_source_for, never a naive
#    is-opener proxy. Real bug fixed 2026-07-08 (contradiction sweep) — the old code used `relay = not
#    is_scene_opener`, which wrongly treated ANY non-opener beat as relay=True even when its predecessor has
#    no rendered/harvested settle frame at all. Proven here: a non-opener beat with NO signed predecessor
#    clip/settle-frame on disk must resolve relay=False (status "no_predecessor_clip"), matching what
#    cb_scene.relay_source_for itself reports — never silently relay=True from the proxy.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_word_count_relay_status_matches_relay_source_for(tmp):
    """Proven by directly intercepting the value check_beat_word_count actually passes to
    cb_segprompt.shipped_prompt's relay= kwarg (via a wrapper), not just by checking it didn't crash —
    a wrapper is required here because BOTH relay=True and relay=False legitimately compile without error
    for this fixture, so 'no compile-failure BLOCK' alone would not catch the regression this test exists
    to guard against (confirmed live: reverting the fix to `relay = not is_scene_opener` still made every
    case in this file pass, because nothing was actually inspecting which relay value got used — this
    version was written specifically so that reversion DOES fail here)."""
    fails = []
    import cb_scene, cb_segprompt as CS

    opener = _clean_beat("9.B1", 9, is_opener=True)
    non_opener = _clean_beat("9.B2", 9, is_opener=False)
    scene_beats = [opener, non_opener]
    scene = _clean_scene(9)
    episode = "Ep9_NoSuchEpisode"

    # Run from a cwd with NO media/ directory at all for this beat code — guarantees no harvested settle
    # frame, no clip, nothing on disk cb_scene.relay_source_for could possibly find (cb_pipeline.vision_for
    # also returns falsy for a beat with no visionPOV, so this legitimately falls through to "does a
    # predecessor clip/harvest exist" — it doesn't, here).
    cwd = os.getcwd()
    os.chdir(tmp)
    try:
        frame_path, status, prev_code = cb_scene.relay_source_for(scene_beats, "9.B2", episode)
        if status == "relay":
            fails.append("test setup error: expected no_predecessor_clip/first with no media on disk, "
                          f"got status={status!r} — fixture no longer isolates the no-predecessor case")

        # A non-opener beat is exactly the case the OLD, buggy proxy (`relay = not is_scene_opener`) would
        # call relay=True — confirm the real, correct status disagrees, so this case genuinely exercises
        # the fix rather than being a tautology that would pass either way.
        naive_proxy_relay = True   # is_scene_opener=False for 9.B2 -> old proxy said relay=True
        real_relay = (status == "relay")
        if naive_proxy_relay == real_relay:
            fails.append("test setup error: naive proxy and real relay_source_for status must DISAGREE here "
                          "for this to actually exercise the fix — they matched, so this case proves nothing")

        # Intercept the actual relay= value check_beat_word_count passes into shipped_prompt.
        seen = {}
        real_shipped_prompt = CS.shipped_prompt
        def _spy(beat, scene, relay=False, prev_carry_marks=None):
            seen["relay"] = relay
            return real_shipped_prompt(beat, scene, relay=relay, prev_carry_marks=prev_carry_marks)
        CS.shipped_prompt = _spy
        try:
            gaps = PF.check_beat_word_count(non_opener, scene, is_scene_opener=False,
                                             prev_carry_marks="the scratch marker",
                                             scene_beats=scene_beats, episode=episode)
        finally:
            CS.shipped_prompt = real_shipped_prompt

        if "relay" not in seen:
            fails.append("check_beat_word_count never called cb_segprompt.shipped_prompt at all")
        elif seen["relay"] != real_relay:
            fails.append(f"check_beat_word_count passed relay={seen['relay']!r} to shipped_prompt, but the "
                          f"real cb_scene.relay_source_for status is {status!r} (relay should be {real_relay!r}) "
                          f"— it has regressed to the naive `not is_scene_opener` proxy")

        if not gaps:
            fails.append("check_beat_word_count should always return exactly one word-count Gap")
        elif gaps[0].field == "v5 word count":
            fails.append(f"check_beat_word_count could not compile the prompt at all: {gaps[0].detail}")
    finally:
        os.chdir(cwd)
    return fails


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# 5a. check_beat_ensemble FLAGS a genuine duplicate-verb pairing (2+ non-economized cast members given the
#     same generic verb in one beat's action text) — cb_craft.check_ensemble_individuation's concrete,
#     checkable "interchangeable ensemble" signal.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _characters_store():
    return {
        "Fuzzby": {"lexicon": {"verbs": ["chases", "whips", "banks", "barrels", "dives", "snaps", "rockets"], "banned": []}},
        "Zenny": {"lexicon": {"verbs": ["hovers", "watches", "sighs", "settles"], "banned": []}},
        "Luna": {"lexicon": {"verbs": ["settles", "lowers", "smooths"], "banned": []}},
    }


def test_ensemble_flags_duplicate_verb(tmp):
    fails = []
    import cb_craft
    characters = _characters_store()
    beat = _clean_beat("9.B1", 9, is_opener=True, characters=["Fuzzby", "Zenny", "Luna"])
    # Fuzzby, Zenny AND Luna all "hold" — a shared, generic verb none of their own lexicons name — with no
    # fidelityAllocation.economized excusing any of them (primary/secondary/economized all real names/"none").
    beat["fidelityAllocation"] = {"primary": "Fuzzby", "secondary": "Zenny", "economized": "none"}
    beat["cuts"] = [{"n": 1, "framing": "wide",
                      "action": "Fuzzby holds a flat look. Zenny holds a flat look. Luna holds a soft smile."}]

    flags = cb_craft.check_ensemble_individuation(beat, characters)
    dup_flags = [f for f in flags if "near-identical action verb" in f.get("detail", "")]
    if not dup_flags:
        fails.append(f"expected a duplicate-verb FLAG for Fuzzby/Zenny/Luna sharing 'holds', got flags={flags}")

    pf_gaps = PF.check_beat_ensemble(beat, characters)
    if not any("near-identical action verb" in g.detail for g in pf_gaps):
        fails.append("cb_preflight.check_beat_ensemble should surface the same duplicate-verb finding as a Gap")
    if any(g.kind == "BLOCK" for g in pf_gaps):
        fails.append("ensemble individuation is FLAG-only (a best-effort heuristic) — must never BLOCK")
    return fails


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# 5b. check_beat_ensemble must NOT flag a character correctly marked 'economized' in fidelityAllocation, even
#     when that character shares a generic/duplicate verb with another economized character — THE
#     FIDELITY-ALLOCATION LAW's whole point (rule 46/49): an author-declared "deliberately generic this beat"
#     character is excused from the individuation bar, not a fresh gap to re-litigate.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_ensemble_excuses_economized_character(tmp):
    fails = []
    import cb_craft
    characters = _characters_store()
    beat = _clean_beat("9.B2", 9, is_opener=False, characters=["Fuzzby", "Zenny", "Luna"])
    # Zenny and Luna are BOTH explicitly economized (background this beat); only Fuzzby is real cast (primary).
    # Zenny+Luna sharing a generic "holds" verb is exactly what "economized" is FOR — must not flag.
    beat["fidelityAllocation"] = {"primary": "Fuzzby", "secondary": "none", "economized": "Zenny, Luna"}
    beat["cuts"] = [{"n": 1, "framing": "wide",
                      "action": "Fuzzby rockets past. Zenny holds a flat look. Luna holds a soft smile."}]

    flags = cb_craft.check_ensemble_individuation(beat, characters)
    dup_flags = [f for f in flags if "near-identical action verb" in f.get("detail", "")]
    if dup_flags:
        fails.append(f"Zenny+Luna are BOTH economized — sharing a generic verb must NOT be flagged, got: {dup_flags}")

    # Also confirm the "nobody traces to their own lexicon" flag is likewise excused for the economized pair —
    # only non-economized cast (here, just Fuzzby, who DOES hit his own lexicon verb "rockets") is graded, and
    # with fewer than 3 non-economized names, that flag's own >=3 threshold can't even fire.
    trace_flags = [f for f in flags if "non-economized cast members" in f.get("detail", "")]
    if trace_flags:
        fails.append(f"only Fuzzby is non-economized here (below the >=3 threshold) — should not fire, got: {trace_flags}")

    pf_gaps = PF.check_beat_ensemble(beat, characters)
    if pf_gaps:
        fails.append(f"cb_preflight.check_beat_ensemble should report zero gaps once the shared verb is properly economized, got: {[(g.field, g.detail) for g in pf_gaps]}")
    return fails


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
CASES = [
    ("clean beat/scene passes with zero BLOCKs", test_clean_beat_passes),
    ("missing carryMarks (technical) is caught", test_missing_technical_field_caught),
    ("blank kidRead (creative) is caught", test_blank_creative_field_caught),
    ("word-count check derives relay via cb_scene.relay_source_for, not an is-opener proxy", test_word_count_relay_status_matches_relay_source_for),
    ("check_beat_ensemble flags a genuine duplicate-verb pairing", test_ensemble_flags_duplicate_verb),
    ("check_beat_ensemble excuses a correctly-economized character", test_ensemble_excuses_economized_character),
]


def main():
    tmp = tempfile.mkdtemp(prefix="cb_preflight_test_")
    bad = 0
    try:
        for label, fn in CASES:
            case_tmp = tempfile.mkdtemp(dir=tmp)
            try:
                fails = fn(case_tmp)
            except Exception as e:
                fails = [f"EXCEPTION: {type(e).__name__}: {e}"]
            if fails:
                bad += 1
                print(f"FAIL  {label}")
                for f in fails:
                    print(f"        - {f}")
            else:
                print(f"PASS  {label}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if bad:
        print(f"{bad}/{len(CASES)} CASE(S) FAILED")
        return 1
    print(f"ALL {len(CASES)} CASES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
