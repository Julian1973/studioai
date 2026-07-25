#!/usr/bin/env python3
"""test_cb_engine.py — zero-cost proof of the hybrid Director Engine (cb_engine.py v2).

Covers: every deterministic validator check (verbatim dialogue, dropped/duplicated lines,
speaker visibility, timing, relay-source integrity, mark/prop drift across a relay join,
continuity cast coverage, the BIG-comedy physical-staging contract), the Law-6 spoken-words
guard on BOTH compiled artifacts, the rule-5 no-appearance guarantee of the compilers'
own fixed text, slot-map consistency, and the anchor contracts shipping verbatim.
No LLM or generation call is ever made (compile paths asserted under a tripwire).

    pytest test_cb_engine.py -q
"""
import copy
import pytest

import cb_engine as E


# ── fixtures ────────────────────────────────────────────────────────────────────────────
CFG = {"Fuzzby": {"sizeRank": 2, "avoid": "bee"}, "Zenny": {"sizeRank": 3, "avoid": "bee"},
       "Keen": {"sizeRank": 5}, "Keen's Mum": {"sizeRank": 4}}

BEATS = [
    {"beatCode": "1.B1", "comedyMode": "BIG", "storyBeat": "Fuzzby crashes.",
     "cuts": [{"framing": "wide", "action": "Fuzzby rockets along.",
               "dialogue": "FUZZBY: Nailed it.", "delivery": "proud"},
              {"framing": "two-shot", "action": "Zenny watches.",
               "dialogue": "ZENNY: Fuzzby… why are you humming?", "delivery": "deadpan"}]},
]


def _state(chars, marks=None, props=None):
    return E.ContinuityState(lighting="warm morning", cameraSide="left of the lane",
                              characters=[E.CharacterState(
                                  character=c, screenZone="frame-left", facing="right",
                                  pose="mid-hover", expression="bright",
                                  visibleMarks=list(marks or []), heldProps=list(props or []))
                                  for c in chars])


def _shot(shot_id="1.B1.S1", source="opener", src_id=None, chars=("Fuzzby",),
          lines=(), binding=None, staging=None, dur=6.0, marks_in=None, marks_out=None,
          transition=None, cut_pace="single_continuous_take", internal_cuts=(),
          composed_of=()):
    return E.Shot(
        shotId=shot_id, beatCode="1.B1", durationSec=dur, purpose="the launch",
        performanceAssignment="Fuzzby rockets between blossoms, clips a stem, wobbles, recovers.",
        camera="Wide tracking, bee height", openingPose="Fuzzby mid-launch outside the flower",
        sourceType=source, sourceShotId=src_id, cutInMotivation=None if src_id is None else "matched action",
        transitionType=transition, cutPace=cut_pace, internalCuts=list(internal_cuts),
        composedOf=list(composed_of),
        dialogueBinding=binding, dialogueLines=list(lines), visualPayoff="He nearly grazes the leaf",
        physicalStaging=staging, prohibited=[], charactersInFrame=list(chars),
        continuityIn=_state(chars, marks=marks_in), continuityOut=_state(chars, marks=marks_out))


def _line(speaker="Fuzzby", text="Nailed it.", start=1.0, end=2.5):
    return E.DialogueLine(speaker=speaker, exactText=text, delivery="proud, chest out",
                          startSec=start, endSec=end)


STAGING = E.PhysicalStaging(
    staysVisible="Fuzzby's whole silhouette above the petals at all times",
    contactAndWeight="chest hits the leaf; the leaf bends, stores force, springs back",
    payoffShape="he pops upward into a proud hover", prohibitedStaging=["vanishing into the flower"])


def _design(shots):
    st = E.DirectorStatement(audienceFeeling="joy", whoseScene="Fuzzby", emotionalChange="pride",
                              theLaugh="the crash", visualSurprise="the leaf", carryForward="the hum")
    return E.SceneShotList(statement=st, shots=shots)


def _clean_design():
    s1 = _shot("1.B1.S1", "opener", chars=("Fuzzby", "Zenny"),
               lines=[_line()], binding="FUZZBY speaks with breathless pride",
               staging=STAGING, marks_out=["pollen dust"])
    # THE SIMPLIFICATION (2026-07-17): the scene's true first shot has nothing to inherit —
    # typed absence (None), matching what design_scene's mechanical clear produces. A
    # "clean" design is one where this is already correctly cleared.
    s1.continuityIn = None
    s2 = _shot("1.B1.S2", "relay", src_id="1.B1.S1", chars=("Fuzzby", "Zenny"),
               lines=[_line("Zenny", "Fuzzby… why are you humming?", 1.0, 3.5)],
               binding="ZENNY speaks with dry deadpan", marks_in=["pollen dust"],
               marks_out=["pollen dust"])
    return _design([s1, s2])


def _codes(report):
    return {i["code"] for i in report["issues"] if i["severity"] == "ERROR"}


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Tripwire: nothing in this suite may ever fire a real LLM call."""
    def boom(*a, **k):
        raise RuntimeError("TRIPWIRE: LLM call attempted inside zero-cost test")
    monkeypatch.setattr(E.cb_llm, "structured", boom)


# ── validator ───────────────────────────────────────────────────────────────────────────
def test_clean_design_passes():
    report = E.validate_scene_design(_clean_design(), BEATS, CFG)
    assert report["passed"], report["issues"]


def test_dropped_line_blocks():
    d = _clean_design()
    d.shots[1].dialogueLines = []
    d.shots[1].dialogueBinding = None
    assert "DIALOGUE_LINE_DROPPED" in _codes(E.validate_scene_design(d, BEATS, CFG))


def test_reworded_line_blocks_as_not_verbatim():
    d = _clean_design()
    d.shots[0].dialogueLines[0].exactText = "Totally nailed it."
    codes = _codes(E.validate_scene_design(d, BEATS, CFG))
    assert "DIALOGUE_NOT_VERBATIM" in codes and "DIALOGUE_LINE_DROPPED" in codes


def test_duplicated_line_blocks():
    d = _clean_design()
    d.shots[1].dialogueLines.append(_line())   # Fuzzby's line assigned twice
    assert "DIALOGUE_LINE_DUPLICATED" in _codes(E.validate_scene_design(d, BEATS, CFG))


def test_speaker_not_visible_blocks():
    d = _clean_design()
    d.shots[0].charactersInFrame = ["Zenny"]
    d.shots[0].continuityIn = _state(["Zenny"])
    d.shots[0].continuityOut = _state(["Zenny"], marks=["pollen dust"])
    assert "SPEAKER_NOT_VISIBLE" in _codes(E.validate_scene_design(d, BEATS, CFG))


def test_dialogue_overrun_and_bad_timing_block():
    d = _clean_design()
    d.shots[0].dialogueLines[0].endSec = 99.0
    codes = _codes(E.validate_scene_design(d, BEATS, CFG))
    assert "DIALOGUE_OVERRUN" in codes
    d = _clean_design()
    d.shots[0].dialogueLines[0].startSec = 3.0
    d.shots[0].dialogueLines[0].endSec = 2.0
    assert "INVALID_DIALOGUE_TIMING" in _codes(E.validate_scene_design(d, BEATS, CFG))


def test_relay_source_integrity():
    d = _clean_design()
    d.shots[1].sourceShotId = None
    assert "RELAY_WITHOUT_SOURCE" in _codes(E.validate_scene_design(d, BEATS, CFG))
    d = _clean_design()
    d.shots[1].sourceShotId = "9.B9.S9"
    assert "INVALID_RELAY_SOURCE" in _codes(E.validate_scene_design(d, BEATS, CFG))
    d = _clean_design()
    d.shots[0].sourceType = "relay"
    d.shots[0].sourceShotId = "1.B1.S2"    # forward reference — not an earlier shot
    codes = _codes(E.validate_scene_design(d, BEATS, CFG))
    assert "FIRST_SHOT_NOT_OPENER" in codes and "INVALID_RELAY_SOURCE" in codes


def test_mark_drift_across_relay_join_blocks():
    d = _clean_design()
    d.shots[1].continuityIn = _state(["Fuzzby", "Zenny"])   # pollen dust vanished across the cut
    assert "MARK_DRIFT" in _codes(E.validate_scene_design(d, BEATS, CFG))


def test_prop_drift_across_relay_join_blocks():
    d = _clean_design()
    d.shots[0].continuityOut.characters[0].heldProps = ["a pollen clump"]
    assert "PROP_DRIFT" in _codes(E.validate_scene_design(d, BEATS, CFG))


def test_continuity_cast_incomplete_blocks():
    d = _clean_design()
    # shots[0] is the scene's true opener (continuityIn=None, typed absence) — this check
    # exercises a shot with real continuityIn, so it targets shots[1] instead.
    d.shots[1].continuityIn.characters = d.shots[1].continuityIn.characters[:1]
    assert "CONTINUITY_CAST_INCOMPLETE" in _codes(E.validate_scene_design(d, BEATS, CFG))


def test_opener_continuity_in_not_cleared_blocks():
    """2026-07-17 (THE SIMPLIFICATION): if the scene's first shot somehow keeps a real
    continuityIn (the mechanical clear didn't run, or a reloaded/hand-edited package
    overwrote it), that's a hard validation error, not a silently-accepted state."""
    d = _clean_design()
    d.shots[0].continuityIn = _state(["Fuzzby", "Zenny"])
    assert "OPENER_CONTINUITY_IN_NOT_CLEARED" in _codes(E.validate_scene_design(d, BEATS, CFG))


def test_continuity_in_missing_for_non_opener_blocks():
    """Typed absence is valid ONLY for the scene's own first shot — a later shot with
    continuityIn=None is a real gap, not a legitimate 'nothing inherited' state."""
    d = _clean_design()
    d.shots[1].continuityIn = None
    assert "CONTINUITY_IN_MISSING" in _codes(E.validate_scene_design(d, BEATS, CFG))
    # the relay-join mark/prop check must degrade gracefully on this same malformed state,
    # never crash with an AttributeError chasing .characters off None
    report = E.validate_scene_design(d, BEATS, CFG)
    assert report is not None and not report["passed"]


def test_design_scene_mechanical_clear_is_pure_and_idempotent():
    """_clear_opener_continuity_in (design_scene's own mechanical override, mirroring
    cb_creative.production_detail's identical pattern) needs no LLM call — proven directly
    against the tripwired fixture. Clears position 0 only, regardless of its prior value,
    and is a no-op on an empty shot list."""
    d = _clean_design()
    d.shots[0].continuityIn = _state(["Fuzzby", "Zenny"])   # simulate an un-cleared LLM draft
    E._clear_opener_continuity_in(d)
    assert d.shots[0].continuityIn is None
    assert d.shots[1].continuityIn is not None               # untouched
    empty = E.SceneShotList(statement=d.statement, shots=[])
    E._clear_opener_continuity_in(empty)                      # empty list: no crash


def test_big_comedy_beat_requires_physical_staging():
    d = _clean_design()
    d.shots[0].physicalStaging = None
    assert "MISSING_PHYSICAL_STAGING" in _codes(E.validate_scene_design(d, BEATS, CFG))


def test_binding_lines_consistency():
    d = _clean_design()
    d.shots[0].dialogueBinding = None
    assert "BINDING_MISSING" in _codes(E.validate_scene_design(d, BEATS, CFG))


def test_unknown_character_blocks():
    d = _clean_design()
    d.shots[0].charactersInFrame = ["Fuzzby", "Bob The Impostor"]
    assert "UNKNOWN_CHARACTER" in _codes(E.validate_scene_design(d, BEATS, CFG))


# ── compilers: the two locked laws, mechanically guaranteed ─────────────────────────────
def test_law6_no_spoken_words_in_either_prompt():
    """GOLD BUILD UPDATE (2026-07-24): compile_shot_contract now emits the SOURCE-MATERIAL
    brief, where dialogue appears BY DESIGN as labelled material under THE VERBATIM LAW —
    the fireability protection moved to cb_render.check_formula_structure, which must
    REFUSE this brief (it is never a fireable prompt). The keyframe compiler is unchanged
    and still Law-6-clean."""
    import cb_render as R
    d = _clean_design()
    for sh in d.shots:
        prompt, _, _ = E.compile_shot_contract(sh, {}, CFG)
        assert prompt.startswith("SOURCE MATERIAL")
        assert "DIALOGUE — THE AUDIO LAW" in prompt
        for ln in sh.dialogueLines:
            assert ln.exactText in prompt          # material, labelled, verbatim
        with pytest.raises(R.Refused, match="THE FORMULA GATE"):
            R.check_formula_structure(prompt, sh.dialogueLines, refuse_prefix="REFUSED — test")
    kf, _, _ = E.compile_keyframe_prompt(d.shots[0], {}, CFG)
    assert "nailed it" not in kf.lower()


def test_law6_guard_fires_loud_on_a_leak():
    sh = _clean_design().shots[0]
    with pytest.raises(AssertionError, match="LAW 6"):
        E._assert_no_spoken_words("He shouts nailed it. proudly", sh, "test artifact")


def test_exact_words_live_only_in_the_audio_brief():
    sh = _clean_design().shots[0]
    brief = E.compile_audio_brief(sh)
    assert "Nailed it." in brief and "@Audio1" in brief
    assert E.compile_audio_brief(_shot(lines=())) is None


def test_anchor_contracts_ship_verbatim():
    d = _clean_design()
    opener, _, _ = E.compile_shot_contract(d.shots[0], {}, CFG)
    relay, _, _ = E.compile_shot_contract(d.shots[1], {}, CFG)
    assert E.OPENER_ANCHOR[:-1] in opener and E.RELAY_ANCHOR[:-1] not in opener
    assert E.RELAY_ANCHOR[:-1] in relay and 'approved opening frame' not in relay


def test_gag_negatives_reach_the_internal_constraints_line():
    # a bare authored phrase is never output bare: it gains an explicit "no " (never stripped).
    # Option D: the constraints line is the INTERNAL contract, not the provider brief.
    line, _ = E.hard_constraints(_clean_design().shots[0], CFG)
    assert "no vanishing into the flower" in line.split("Hard constraints:")[-1]


def test_conditional_constraints_every_trigger_and_its_absence():
    """Julian's ruling (2026-07-16): each proven constraint ships ONLY on its explicit trigger.
    One positive and one negative case per trigger; dedup happens later, by ID."""
    texts = lambda pairs: [t for _, t in pairs]
    talky = _clean_design().shots[0]
    silent = _shot("1.B1.S9", "opener", chars=("Fuzzby",), lines=(), staging=None)
    silent.performanceAssignment = "Fuzzby hovers between blossoms, weaving a slow arc."
    silent.visualPayoff = "He circles the tallest bloom"
    silent.openingPose = "Fuzzby mid-hover by the blossom"
    got_t = texts(E._conditional_constraints(talky, CFG))
    got_s = texts(E._conditional_constraints(silent, CFG))
    assert "no invented background voices" in got_t and "no foreign-language speech" in got_t
    assert "no invented background voices" not in got_s and "no foreign-language speech" not in got_s
    # bee trigger: bee cast gets wing/crystal items; all-bear cast does not
    bears = _shot("1.B1.S8", "opener", chars=("Keen",), lines=(), staging=None)
    bears.performanceAssignment = "Keen hovers a paw over the water, waiting."
    bears.openingPose = "Keen at the water's edge"
    bears.visualPayoff = "His reflection stills"
    got_b = texts(E._conditional_constraints(bears, CFG))
    assert "wings continue moving while airborne" in got_t and "no crystals on the bees" in got_t
    assert "wings continue moving while airborne" not in got_b and "no crystals on the bees" not in got_b
    # ground-contact trigger: crash/land text gets it; pure-hover text does not
    crash = _shot("1.B1.S7", "opener", chars=("Fuzzby",), lines=(), staging=None)
    crash.performanceAssignment = "Fuzzby crashes chest-first into the leaf and lands hard."
    assert "no floating or sinking through ground" in texts(E._conditional_constraints(crash, CFG))
    assert "no floating or sinking through ground" not in got_s
    # gag-physics trigger: staged shot gets inflation/deflation; unstaged does not
    assert "no body inflation" in got_t and "no full-body deflation" in got_t
    assert "no body inflation" not in got_s


# ── the full-sentence fix (2026-07-22): a positive multi-clause authored NOTE must never
#    get a mechanical "no " jammed onto its front — pinned to the exact real S1.SH2 content
#    that surfaced this bug live in a compiled Scene-1 prompt.
def test_full_sentence_authored_item_never_gets_a_false_no_prefix():
    sh = _clean_design().shots[0]
    sh.prohibited = [
        "Camera must stay still with Zenny; do not grant Fuzzby a clean heroic showcase.",
        "Zenny’s delivery and body remain economical and near-still, with no big "
        "punchline reaction.",
        "Fuzzby’s hover never fully settles; his forced dignity must be undercut by "
        "small visible corrections.",
    ]
    line, _ = E.hard_constraints(sh, CFG)
    assert "no Camera must stay still" not in line, \
        "a positive requirement must never be corrupted into a nonsense double negative"
    assert "Camera must stay still with Zenny; do not grant Fuzzby a clean heroic " \
           "showcase" in line, "a full authored sentence ships exactly as authored"
    assert "Zenny’s delivery and body remain economical and near-still, with no " \
           "big punchline reaction" in line
    assert "no Zenny’s delivery" not in line
    assert "Fuzzby’s hover never fully settles; his forced dignity must be " \
           "undercut by small visible corrections" in line
    # a bare, unpunctuated phrase (no terminal punctuation, no internal clause) still gets
    # the synthetic "no " prefix exactly as before — this fix narrows the old behaviour,
    # it does not remove it
    assert E._explicit_constraint("extra characters") == "no extra characters"
    assert E._explicit_constraint("do not add extra spins") == "do not add extra spins"


# ── Julian's bounded correction (2026-07-16): negation, dedup, abstraction, cap priority ─
def test_negation_never_stripped_in_internal_contract():
    sh = _clean_design().shots[0]
    sh.prohibited = ["Do not let Zenny react broadly.", "Do not resolve the crash here."]
    line, _ = E.hard_constraints(sh, CFG)
    tail = line.split("Hard constraints:")[-1]
    assert "Do not let Zenny react broadly" in tail          # authored wording verbatim
    assert "Do not resolve the crash here" in tail
    assert "Negative:" not in line                            # heading replaced
    # the bare phrase never appears WITHOUT its own negation immediately in front of it
    assert "; let Zenny react broadly" not in line and ": let Zenny react broadly" not in line


def test_option_d_planning_intent_stays_internal_constraints_now_ship():
    """Julian's Option D (2026-07-16): PLANNING INTENT (purpose, creative rationale) stays in
    the internal contract, never repeated at the provider.

    CORRECTED 2026-07-20 (Julian's own worked prompt, "No extra characters, additional
    speech, redesigns, crystals, subtitles or text."): the OTHER half of Option D's original
    premise — that AUTHORED CONSTRAINTS also never reach the brief — is reversed here.
    hard_constraints() was always the right, deterministic computation (proven correct by
    this same test since 2026-07-16); what changed is that its own line now ships as part of
    the brief instead of living only in internalConstraints, closing the gap Option D's own
    docstring named as "a separate, undecided question" the day it was written. Authored
    shot.prohibited items are no longer silent internal-only notes — they now ship, verbatim,
    inside the same Hard constraints line, matching every machine-computed item beside them."""
    sh = _clean_design().shots[0]
    sh.prohibited = ["Do not let Zenny react broadly.", "Do not resolve the crash here."]
    line, prov = E.hard_constraints(sh, CFG)
    assert all(a in line for a in ("Do not let Zenny react broadly",
                                    "Do not resolve the crash here"))
    brief, wc, _ = E.compile_shot_contract(sh, {}, CFG)
    assert "let Zenny react broadly" in brief                 # NOW ships, ships verbatim
    assert "Hard constraints:" in brief
    assert "the pose itself" not in brief and sh.purpose not in brief  # planning stays internal
    # GOLD BUILD UPDATE (2026-07-24): the source-material brief has no word ceiling (the
    # 210-word Option-D lean band belonged to the retired fireable-prose shape) — the brief
    # is labelled facts now, and the labelled sections replace the old mechanical sentences.
    assert brief.startswith("SOURCE MATERIAL")
    assert E.OPENER_ANCHOR[:-1] in brief and "OPENING ANCHOR" in brief   # exact opening anchor
    assert "REFERENCES:" in brief                             # one declared job per reference
    assert "DIALOGUE — THE AUDIO LAW" in brief             # audio/dialogue material section
    assert "HARD CONSTRAINTS" in brief
    assert "screen sides" not in brief          # 2026-07-17: no longer a default on every shot
    # the gag's own visibility contract ships as its labelled fact, verbatim
    assert ("GAG PHYSICS — stays visible: Fuzzby's whole silhouette above the petals "
            "at all times") in brief


def test_dedup_by_canonical_id_not_fuzzy_text():
    sh = _clean_design().shots[0]                             # dialogue shot: audio trigger fires
    line, prov = E.hard_constraints(sh, CFG)
    assert "no invented voices" in line                       # universal, always
    assert "invented background voices" not in line           # subsumed by canonical ID
    assert prov["deduplicated"] == ["no_invented_background_voices"]
    assert E.SUBSUMES["no_invented_voices"] == {"no_invented_background_voices"}


def test_abstract_direction_fails_validation_never_rewritten():
    d = _clean_design()
    d.shots[0].performanceAssignment = ("Zenny's efficient hover silently measures the "
                                         "difference between his confidence and his control.")
    report = E.validate_scene_design(d, BEATS, CFG)
    hits = [i for i in report["issues"] if i["code"] == "ABSTRACT_DIRECTION"]
    assert hits and not report["passed"]
    assert "1.B1.S1" in hits[0]["path"] and "measures the difference" in hits[0]["message"]
    # and the source text was NOT auto-rewritten — it fails, a human corrects it
    assert "measures the difference" in d.shots[0].performanceAssignment
    clean = _clean_design()
    assert not [i for i in E.validate_scene_design(clean, BEATS, CFG)["issues"]
                if i["code"] == "ABSTRACT_DIRECTION"]


def test_cap_applies_only_to_conditionals_authored_never_dropped():
    sh = _clean_design().shots[0]                             # staging carries 1 authored gag item
    sh.prohibited = ["Do not add extra spins.", "Do not move Zenny into the impact.",
                      "Do not smear pollen marks yet.", "Do not shake the camera.",
                      "Do not brighten the light."]           # 5 authored + 1 gag = 6 authored
    line, prov = E.hard_constraints(sh, CFG)
    for a in prov["authored"]:
        assert E._explicit_constraint(a) in line              # every authored item ships
    assert len(prov["authored"]) == 6                         # none dropped, cap never touches them
    assert len(prov["conditional"]) <= E.CONDITIONAL_CAP      # cap hits conditionals only
    for cid in prov["capped_out"]:
        assert cid not in prov["authored"]                    # only conditional IDs ever cap out
    for _, t in E.UNIVERSAL_CONSTRAINTS:
        assert t in line                                      # the five, always


def test_word_overflow_compiles_clean_with_no_llm_call(monkeypatch):
    """2026-07-21 correction (Julian's direct ruling — "take all the straightjackets off"):
    the hard word ceiling is REMOVED from compile_shot_contract. A long, real, authored
    direction now compiles into a real, working prompt instead of being refused outright —
    length was never the actual quality problem this project found (over-specified
    negatives/camera JSON were); trust the Director's real direction. What stays true and
    still worth proving: compilation is fully deterministic — no LLM is ever invoked to
    auto-compress or rewrite a long brief, at any length."""
    import cb_llm
    def _boom(*a, **k):
        raise AssertionError("compile_shot_contract must never call an LLM, at any length")
    monkeypatch.setattr(cb_llm, "structured", _boom)
    sh = _clean_design().shots[0]
    long_direction = " ".join(["Fuzzby weaves between the tall blossoms"] * 60)
    sh.performanceAssignment = long_direction
    prompt, wc, slots = E.compile_shot_contract(sh, {}, CFG)
    assert wc > E.MAX_SHOT_PROMPT_WORDS                        # genuinely long, never trimmed
    assert "Fuzzby weaves between the tall blossoms" in prompt  # the real content ships


# ── THE 2026-07-17 SECOND FIELD-BUDGET CORRECTION (Julian's explicit decision,
# PIPELINE_CUTOVER_LEDGER.md §10): performanceAssignment's own isolated 50-word cap is
# REMOVED from FIELD_WORD_BUDGETS. The four proofs below pin exactly what stays true and
# what changes: the governing constraint is now the COMPILED brief's own real ceiling
# (MAX_SHOT_PROMPT_WORDS) plus the COMPILABILITY check, never a second, field-isolated cap;
# Law 6 and abstract-direction validation are untouched.
def test_a_seventy_to_ninety_word_physical_performance_passes_within_the_210_word_brief():
    """PROOF 1: a real, Gate-5-shaped 72-92-word physicalPerformance — exactly the length
    range found on the real, approved Ep1 Scene 1 shots — must PASS validate_scene_design
    (no FIELD_OVERBUDGET) whenever the COMPILED brief stays within the real 210-word
    ceiling. FIELD_WORD_BUDGETS no longer has an entry for performanceAssignment at all."""
    assert "performanceAssignment" not in E.FIELD_WORD_BUDGETS
    d = _clean_design()
    # a real Gate-5-shaped body-first direction, 76 words — verbatim shape of the real
    # approved S1.SH1 physicalPerformance text this correction exists to unblock.
    d.shots[0].performanceAssignment = (
        "Fuzzby flies from the belief that speed equals rank: chest leading, wings "
        "overworking, tiny course-corrections arriving a beat after his body needs them. "
        "The leaf takes his full committed weight, bends deep, then springs him off-line; "
        "he pinballs back into hover with paws briefly searching for balance before he "
        "snaps his chest proud and pretends the wobble was part of the job. Zenny does not "
        "chase the impact; her stillness makes his recovery look even louder.")
    assert 70 <= len(d.shots[0].performanceAssignment.split()) <= 92
    report = E.validate_scene_design(d, BEATS, CFG)
    assert "FIELD_OVERBUDGET" not in _codes(report), report["issues"]
    assert report["passed"], report["issues"]
    prompt, wc, _ = E.compile_shot_contract(d.shots[0], {}, CFG)
    # 2026-07-21: the wc<=MAX_SHOT_PROMPT_WORDS assertion this line used to carry is now
    # stale by design, not by regression — QUALITY_LINE (the same night's style-law-plus-
    # craft-line addition, Julian's own techhalla-example comparison) adds real content to
    # every compiled shot, and the sibling test right below this one already proves a shot
    # legitimately exceeding this now-informational-only ceiling still compiles and passes
    # validation. wc itself is still returned and still meaningful to look at; it just isn't
    # a pass/fail gate here or anywhere else in this module (task #409's own ruling).
    assert wc > 0


def test_a_brief_exceeding_210_words_compiles_and_passes_validation():
    """PROOF 2, corrected 2026-07-21: the per-field cap was already gone; the overall
    compiled-brief ceiling is now gone too (Julian's direct ruling against straightjacketing
    real creative direction). A shot whose performanceAssignment is long enough to blow the
    old 210-word ceiling now compiles cleanly and validate_scene_design's own COMPILABILITY
    check passes it — SHOT_OVERBUDGET no longer exists as a possible finding at all; only a
    genuine compile guard (e.g. a Law 6 leak) can still fail this check."""
    d = _clean_design()
    d.shots[0].performanceAssignment = " ".join(
        ["Fuzzby weaves between the tall blossoms, wings beating hard, chest leading"] * 15)
    prompt, wc, slots = E.compile_shot_contract(d.shots[0], {}, CFG)
    assert wc > E.MAX_SHOT_PROMPT_WORDS
    report = E.validate_scene_design(d, BEATS, CFG)
    codes = _codes(report)
    assert "SHOT_OVERBUDGET" not in codes                       # the code no longer exists
    assert "COMPILE_GUARD" not in codes                         # not a genuine compile failure


def test_verbatim_dialogue_inside_performance_assignment_still_refuses():
    """PROOF 3, RE-POINTED FOR THE GOLD BUILD (2026-07-24): compile_shot_contract no longer
    runs _assert_no_spoken_words — the source-material brief carries dialogue BY DESIGN
    under THE VERBATIM LAW section, so a performanceAssignment quoting the locked line
    compiles clean. The FIREABILITY protection now lives in cb_render.check_formula_
    structure (plus the department layer): the source brief itself must be refused as a
    prompt. compile_keyframe_prompt's own Law-6 guard is unchanged (proven by
    test_law6_guard_fires_loud_on_a_leak and the keyframe tests below)."""
    import cb_render as R
    d = _clean_design()
    d.shots[0].performanceAssignment = (
        'Fuzzby commits fully, chest leading into the recovery, and declares "Nailed it." '
        "as the whole beat turns on it.")
    brief, _, _ = E.compile_shot_contract(d.shots[0], {}, CFG)
    assert "DIALOGUE — THE AUDIO LAW" in brief
    assert "Nailed it." in brief                              # legitimate source material now
    with pytest.raises(R.Refused, match="THE FORMULA GATE"):
        R.check_formula_structure(brief, d.shots[0].dialogueLines,
                                  refuse_prefix="REFUSED — test")


def test_field_word_budgets_now_empty_and_generic_lookup_still_safe():
    """The removal is structural, not a special-case: FIELD_WORD_BUDGETS is now an empty
    dict, and both call sites that read it (_field_rejections' repair-loop check,
    validate_scene_design's own FIELD_OVERBUDGET check) use .get() against it — neither
    raises, and neither field-level budget check can ever fire again for ANY field name,
    proving no replacement field limit was introduced anywhere."""
    assert E.FIELD_WORD_BUDGETS == {}
    long_text = " ".join(["word"] * 200)
    assert E._field_rejections("performanceAssignment", long_text) == []
    assert E._field_rejections("visualPayoff", long_text) == []


def test_one_consistent_anchor_matching_style_rule():
    """Points 9 + Option D (2026-07-16): opener and relay both anchor style to their own @图1.

    CORRECTED 2026-07-21 (Julian, comparing a real AAA-grade example prompt against ours):
    the "never Pixar-caliber, never squash-and-stretch" half of this test's original premise
    was itself the gap it should have been catching — this compiler's _style_line used to
    ship a thinner, disconnected hardcoded string instead of the show's own real, already-
    approved style law (shows/crystal-bears/laws/style.txt, rule 75's "Original 3D CGI
    animation, ages 4-8, Pixar-caliber: real weight, squash-and-stretch...") that every OTHER
    consumer in this pipeline already quoted. Now every compiled prompt (shot and keyframe
    alike) carries that same law verbatim — this test now asserts it's PRESENT, the opposite
    of the original assertion, which was pinning down the old, disconnected behaviour rather
    than a real requirement."""
    d = _clean_design()
    opener, _, _ = E.compile_shot_contract(d.shots[0], {}, CFG)
    relay, _, _ = E.compile_shot_contract(d.shots[1], {}, CFG)
    for p in (opener, relay):
        assert "Stylised feature-quality 3D CGI matching @图1." in p
        assert "Pixar-caliber" in p and "squash-and-stretch" in p
        assert "only for the set" in p                        # the plate has a declared job
    # GOLD BUILD UPDATE (2026-07-24): the keyframe compiler now emits the OPENING-FRAME
    # source brief carrying the SAME one style law verbatim — one consistent anchor, both
    # artifacts, no divergent second style string anywhere.
    kf, _, _ = E.compile_keyframe_prompt(d.shots[0], {}, CFG)
    assert "Stylised feature-quality 3D CGI matching @图1." in kf
    assert "Pixar-caliber" in kf and "squash-and-stretch" in kf


def test_concise_anchors_no_antihold_boilerplate():
    """Option D (2026-07-16): concise anchors; no compiled boilerplate about pose holding —
    the shot's own observable direction decides whether a pose continues.

    CORRECTED 2026-07-19: RELAY_ANCHOR's own wording changed from "continue the new action
    immediately" to "matched for identity, position and lighting" — the anchor's job is
    stating what carries over (state), never what happens next (that's the shot's own camera/
    action clause, concatenated directly after it in compile_shot_contract). The old wording
    packed a camera/action instruction into the continuity clause, the exact duplication
    CLAUDE.md rule 51 already named and corrected once for this same anchor line. Still true:
    no pose-holding boilerplate — the shot's own observable direction decides the rest.

    CORRECTED AGAIN 2026-07-20 (Julian, real S1.SH1 footage: "no movement no fast paced...
    no big tumble and correction"): the "no boilerplate about pose holding" premise itself
    was the bug for OPENER_ANCHOR specifically — leaving it entirely bare meant nothing ever
    told the model @图1 is a launch point, not a frame to freeze on, the exact anti-hold
    failure mode this show's own earlier pipeline had already hit and fixed multiple times
    (CLAUDE.md rules 26/51/76). A short, universal, mechanical anti-hold clause on
    OPENER_ANCHOR replaces the old bare wording — still no PER-SHOT boilerplate (nothing
    authored, nothing shot-specific), just one fixed sentence covering every opener. Also
    added: "Single continuous take, no cuts." is now mechanically appended to every shot's
    camera clause in compile_shot_contract (not the anchor itself) — true by construction of
    this one-shot-per-call architecture, stated explicitly so the model never reads ambiguous
    camera language as license to cut between two setups."""
    assert E.OPENER_ANCHOR == ("Begin exactly on @图1, the approved opening frame — motion "
                                "begins immediately, never a resting hold.")
    assert E.RELAY_ANCHOR == ("Begin exactly on @图1, the approved final frame of the previous "
                               "shot, matched for identity, position and lighting.")
    relay, _, _ = E.compile_shot_contract(_clean_design().shots[1], {}, CFG)
    for banned in ("unnecessary hold", "Do not hold the previous pose", "restage"):
        assert banned not in relay
    # GOLD BUILD UPDATE (2026-07-24): the mechanically-appended camera sentence is retired
    # with the fireable prose shape — the same fact now ships as the labelled CUT PACE fact
    # the register writer turns into a one-Shot-1 card.
    assert "CUT PACE: single continuous take — the card is one Shot 1 only" in relay


def test_hard_constraints_line_reaches_the_compiled_prompt():
    """2026-07-20 (Julian's own worked prompt: "No extra characters, additional speech,
    redesigns, crystals, subtitles or text."): hard_constraints() has computed exactly this
    set deterministically since 2026-07-16 (the universal five plus live-triggered
    conditionals) but was deliberately never concatenated into the shipped Seedance brief —
    Option D's own docstring flagged this as "a separate, undecided question." Closed here:
    the SAME computed line, not a hand-typed approximation of it, must now reach the prompt.

    2026-07-22 UPDATE (Julian, live, watching S1.SH1's real render — "no freedom to it...
    we have so many rules in place that stop the creativity of Seedance"): "no camera cut"
    was removed from the universal four (was five) — it forced a single, uncut camera
    vector onto every shot in the show regardless of what the Director actually authored,
    confirmed as a real contributor to the flat, single-note camera work Julian watched.
    Whether a shot cuts internally is the Director's own per-shot cutPace/internalCuts
    choice now, never a machine-wide override — see hard_constraints's own updated comment."""
    shot = _clean_design().shots[0]   # has dialogueLines + winged charactersInFrame
    prompt, _, _ = E.compile_shot_contract(shot, {}, CFG)
    assert "Hard constraints:" in prompt
    assert "no character redesign" in prompt
    assert "no extra characters" in prompt
    assert "no on-screen text" in prompt
    assert "no invented voices" in prompt
    assert "no camera cut" not in prompt
    # conditional: winged cast in frame
    assert "no crystals on the bees" in prompt


def test_hard_constraints_line_matches_the_standalone_function_exactly():
    """The prompt's negative line and the package's own internalConstraints (compile_scene_
    package's hard_constraints(sh, characters_cfg)[0]) must be the identical string — never
    two independently-computed near-copies that could silently drift apart."""
    shot = _clean_design().shots[0]
    prompt, _, _ = E.compile_shot_contract(shot, {}, CFG)
    hc_line, _ = E.hard_constraints(shot, CFG)
    assert hc_line in prompt


def test_contact_and_weight_reaches_the_compiled_prompt():
    """2026-07-20 (Julian, real S1.SH1 footage): physicalStaging.contactAndWeight is the
    gag's actual cause-and-effect chain (what hits what, where it bends, where it rebounds)
    — authored, required on every BIG-comedy beat's gag shot, but previously never reached
    the compiled Seedance brief at all (only staysVisible did, via _render_critical). Must
    now ship verbatim as part of the shot's own action beats."""
    opener, _, _ = E.compile_shot_contract(_clean_design().shots[0], {}, CFG)
    assert "hits the leaf" in opener   # capitalized as a fresh sentence: "Chest hits..."
    assert "springs back" in opener


def test_contact_and_weight_absent_when_not_authored():
    """A shot with no physicalStaging (the common case — only required on a BIG-comedy
    beat's own gag-carrying shot) must compile clean with no crash and no stray text."""
    shot = _clean_design().shots[1]
    shot.physicalStaging = None
    prompt, _, _ = E.compile_shot_contract(shot, {}, CFG)
    assert prompt  # compiles fine


def test_redundant_lip_sync_sentence_is_deduplicated():
    """2026-07-20 (Julian, real S1.SH1 footage): the design LLM sometimes restates the audio
    assignment inside performanceAssignment/visualPayoff's own free prose, duplicating what
    _lip_sync_sentence already generates mechanically from dialogueLines — real wasted budget
    under the 210-word hard ceiling. The duplicate sentence must never survive into the
    compiled prompt; the mechanically-generated one (via _lip_sync_sentence) must."""
    d = _clean_design()
    d.shots[0].performanceAssignment = (
        "Fuzzby rockets between blossoms, clips a stem, wobbles, recovers. "
        "Lip-sync the approved @Audio1 performance exactly; no additional speech.")
    prompt, _, _ = E.compile_shot_contract(d.shots[0], {}, CFG)
    assert prompt.count("no additional speech") == 0
    assert "Fuzzby rockets between blossoms" in prompt
    # GOLD BUILD UPDATE (2026-07-24): the mechanical "Use @Audio1..." sentence belonged to
    # the retired fireable prose; the audio/dialogue contract now ships as the labelled
    # VERBATIM LAW section, which is what survives instead of the stripped duplicate.
    assert "DIALOGUE — THE AUDIO LAW" in prompt


def test_strip_redundant_audio_sentence_leaves_clean_text_untouched():
    text = "Fuzzby rockets between blossoms, clips a stem, wobbles, recovers."
    assert E._strip_redundant_audio_sentence(text) == text
    assert E._strip_redundant_audio_sentence("") == ""
    assert E._strip_redundant_audio_sentence(None) is None


# ── THE OBSERVABLE-DIRECTION REPAIR LOOP (Julian's directive, 2026-07-16) ────────────────
# The five real rejected phrases from Ep1 Scene 1 are the permanent regression fixtures.
REJECTED_PHRASE_FIXTURES = [
    ("1.B1.S3", "until the pose itself becomes the joke"),
    ("1.B2.S2", "sincerely offers the accident as status"),
    ("1.B4.S1", "mistakes the attention as permission for another stunt"),
    ("1.B4.S3", "making the distant rumble feel larger because she refuses to decorate it"),
    ("1.B5.S1", "selling pressure as his specialty"),
]


def test_five_rejected_phrases_stay_caught():
    for shot_id, phrase in REJECTED_PHRASE_FIXTURES:
        assert E._field_abstract_hits(phrase), f"{shot_id} fixture no longer caught: {phrase}"


def test_auto_repair_field_scoped_two_attempts_then_success(monkeypatch):
    import cb_llm
    calls = []
    def fake_structured(system, user, schema, label=""):
        calls.append(label)
        # attempt 1 returns text that is STILL abstract; attempt 2 returns clean direction
        if len([c for c in calls if c.startswith("repair_")]) == 1:
            return E._FieldRepair(text="He sells the moment as his specialty, chest out.")
        return E._FieldRepair(text="Fuzzby pushes his chest forward and holds a fixed smile "
                                     "while Zenny watches without moving.")
    monkeypatch.setattr(cb_llm, "structured", fake_structured)
    d = _clean_design()
    d.shots[0].performanceAssignment = ("Fuzzby wobbles upward, "
                                         "selling pressure as his specialty.")
    before = {f: repr(getattr(d.shots[0], f)) for f in ("purpose", "camera", "durationSec",
                                                          "prohibited", "openingPose")}
    log, esc, final = E.auto_repair_abstract_directions(d, BEATS, CFG)
    assert len(log) == 2 and esc == []                        # attempt 1 rejected, attempt 2 passed
    assert "REJECTED" in log[0]["validationResult"] and "PASSED" in log[1]["validationResult"]
    assert log[0]["original"].endswith("as his specialty.")   # original recorded, never silent
    assert log[1]["model"] and log[1]["promptVersion"] == E.REPAIR_PROMPT_VERSION
    assert "specialty" not in d.shots[0].performanceAssignment
    for f, v in before.items():                               # protected fields untouched
        assert repr(getattr(d.shots[0], f)) == v
    assert not [i for i in final["issues"] if i["code"] == "ABSTRACT_DIRECTION"]


def test_auto_repair_escalates_after_two_failed_attempts(monkeypatch):
    import cb_llm
    monkeypatch.setattr(cb_llm, "structured", lambda *a, **k: E._FieldRepair(
        text="He still mistakes her look as permission."))    # abstract every time
    d = _clean_design()
    original = "Fuzzby mistakes the attention as permission for another stunt."
    d.shots[0].performanceAssignment = original
    log, esc, final = E.auto_repair_abstract_directions(d, BEATS, CFG)
    assert len(log) == E.REPAIR_MAX_ATTEMPTS and len(esc) == 1
    assert d.shots[0].performanceAssignment == original       # never ships a half-repair
    assert not final["passed"]                                # honest red until a human decides


def test_slot_maps_render_vs_keyframe():
    sh = _clean_design().shots[0]
    render = E.reference_slots(sh, CFG)
    assert render["@图1"] == "opening keyframe" and render["@Audio1"] == "voice track"
    assert render["@图2"] == "Fuzzby" and render["@图3"] == "Zenny"   # sizeRank order
    assert render["@图4"] == "scene plate"
    kf = E.reference_slots(sh, CFG, for_keyframe=True)
    assert kf["@图1"] == "Fuzzby" and kf["@图3"] == "scene plate" and "@Audio1" not in kf


def test_keyframe_prompt_omits_continuity_paragraph_when_nothing_inherited():
    """2026-07-17 (THE DUPLICATION correction, then THE SIMPLIFICATION): when
    continuityIn is None (typed absence — the scene's true opener, mechanically cleared by
    cb_engine.design_scene, never LLM-authored), the compiled keyframe brief must OMIT the
    'Continuity in:' paragraph entirely rather than print a no-op sentence. A plain `is
    None` check, never a sentinel-string comparison."""
    shot = _clean_design().shots[0]
    shot = shot.model_copy(update={"continuityIn": None})
    kf, wc, _ = E.compile_keyframe_prompt(shot, {}, CFG)
    # GOLD BUILD UPDATE (2026-07-24): the keyframe compiler emits the OPENING-FRAME source
    # brief now — typed absence still means the CONTINUITY IN fact is wholly absent, never
    # a no-op line; the plate's scoped job ships via the reference-role sentence; the old
    # word ceiling belonged to the retired fireable prose shape.
    assert kf.startswith("SOURCE MATERIAL")
    assert "continuity in" not in kf.lower()
    assert "@图4 only for the set" in kf                    # the plate's declared, scoped job
    assert wc > 0


def test_keyframe_prompt_prints_continuity_paragraph_when_real_state_inherited():
    """The opposite case — genuinely inherited state (a real relay, not the sentinel)
    still prints normally, unaffected by the correction above."""
    shot = _clean_design().shots[0]
    real_state = E.ContinuityState(lighting="cooler storm light now reaching the petals",
                                    cameraSide="cooler storm light now reaching the petals",
                                    characters=[])
    shot = shot.model_copy(update={"continuityIn": real_state})
    kf, wc, _ = E.compile_keyframe_prompt(shot, {}, CFG)
    # GOLD BUILD UPDATE (2026-07-24): the inherited state ships as the labelled
    # CONTINUITY IN fact carrying the real content, for the register writer to honour.
    assert "continuity in" in kf.lower()
    assert "cooler storm light" in kf.lower()


def test_keyframe_prompt_is_reference_first_and_appearance_free():
    """2026-07-17 correction (Julian's Gate-B source-contract ruling, S1.SH1's rejected
    keyframe): the universal 'frame a touch wider... room to breathe' compiler nudge is
    REMOVED — it was a real, confirmed root cause of a compiled brief drifting to a wide
    scenic vista instead of the approved composition. Framing now comes solely from
    shot.openingPose (openingImage); the plate is explicitly barred from claiming
    composition or geography, only palette/materials/lighting."""
    kf, wc, _ = E.compile_keyframe_prompt(_clean_design().shots[0], {}, CFG)
    assert "wider" not in kf.lower()                  # the room-to-breathe law is GONE
    # GOLD BUILD UPDATE (2026-07-24): the plate's scoped job now ships via the
    # reference-role sentence ("only for the set" — never composition/geography ownership),
    # and identity stays reference-first, stated as such in the brief's own labels.
    assert "@图4 only for the set" in kf
    assert "identity from references only" in kf
    # rule 5: the compiler's own fixed text never describes appearance
    for banned in ("yellow", "stripe", "spectacles", "glasses", "fur", "fuzzy"):
        assert banned not in kf.lower()


# ── THE HANDOVER-MAPPING CORRECTION (2026-07-17, Julian's audit + consolidation) ────────
# Two genuine source defects, found via cb_handover.py's single-shot handover audit, fixed
# HERE at source (the one narrowly-scoped exception to this file's usual protection) rather
# than as a second compiler layered on top in cb_handover.py — see that module's own
# consolidation note. Both compile_keyframe_prompt and compile_shot_contract are the SOLE
# compilers for their artifacts; nothing duplicates this logic anywhere else.
def _still_shot():
    """A shot whose approved opening state is deliberate STILLNESS, not motion — the S1.SH6
    real-production shape (Zenny already still, before a quiet line), built from this file's
    own fixtures rather than a hand-typed one-off."""
    sh = _shot(chars=("Zenny",))
    sh.openingPose = "Zenny holds motionless on her petal, eyes closed, wings folded flat."
    sh.continuityIn = E.ContinuityState(
        lighting="cooler blue wash settling after the thunder tail", cameraSide="held wide",
        characters=[E.CharacterState(character="Zenny", screenZone="frame-centre", facing="up",
                                      pose="motionless", expression="listening",
                                      visibleMarks=[], heldProps=[])])
    return sh


def test_keyframe_prompt_follows_motion_already_underway_not_a_universal_anticipation():
    """The default fixture's own openingPose ('Fuzzby mid-launch outside the flower') already
    describes motion underway — the compiler must state it plainly, never impose a universal
    'anticipation instant before the action, never the payoff' framing, and never ban 'the
    action already happening' as a negative (both were false universals, removed 2026-07-17)."""
    kf, wc, _ = E.compile_keyframe_prompt(_clean_design().shots[0], {}, CFG)
    assert "mid-launch" in kf
    assert "anticipation instant" not in kf.lower()
    assert "never the payoff" not in kf.lower()
    assert "action already happening" not in kf.lower()
    assert "nearly grazes the leaf" not in kf              # visualPayoff never read


def test_keyframe_prompt_follows_deliberate_stillness_not_forced_motion():
    """THE SAME compiler, given an approved opening state that is deliberate stillness, must
    never inject motion or anticipation language — proving it follows the approved shot
    rather than imposing one posture on every shot (Julian's own S1.SH6 test case)."""
    kf, wc, _ = E.compile_keyframe_prompt(_still_shot(), {}, CFG)
    assert "holds motionless" in kf
    assert "anticipation instant" not in kf.lower()
    assert "never the payoff" not in kf.lower()
    assert "action already happening" not in kf.lower()


def test_keyframe_prompt_states_lighting_and_camera_side_once_when_duplicated():
    """A caller whose own mapping has (degenerately) duplicated one prose sentence into both
    continuityIn.lighting and continuityIn.cameraSide — cb_handover.py's own documented
    INTEGRATION_GAPS limitation — must not see it stated twice in the compiled brief."""
    sh = _shot(chars=("Fuzzby",))
    sh.continuityIn = E.ContinuityState(
        lighting="Warm corridor light, Fuzzby already at speed.",
        cameraSide="Warm corridor light, Fuzzby already at speed.",
        characters=[E.CharacterState(character="Fuzzby", screenZone="frame-left", facing="right",
                                      pose="mid-hover", expression="proud",
                                      visibleMarks=[], heldProps=[])])
    kf, wc, _ = E.compile_keyframe_prompt(sh, {}, CFG)
    # GOLD BUILD UPDATE (2026-07-24): the prose-paragraph dedup belonged to the retired
    # fireable shape — inherited state now ships ONCE, as the single labelled CONTINUITY IN
    # fact (a faithful dump of the typed state), never as two competing prose restatements.
    assert kf.count("CONTINUITY IN") == 1
    assert "Warm corridor light, Fuzzby already at speed" in kf
    # a genuinely distinct pair still ships both, inside that one labelled fact
    sh2 = _shot(chars=("Fuzzby",))
    sh2.continuityIn = E.ContinuityState(
        lighting="Warm corridor light.", cameraSide="Held on the left of the lane.",
        characters=[E.CharacterState(character="Fuzzby", screenZone="frame-left", facing="right",
                                      pose="mid-hover", expression="proud",
                                      visibleMarks=[], heldProps=[])])
    kf2, wc2, _ = E.compile_keyframe_prompt(sh2, {}, CFG)
    assert kf2.count("CONTINUITY IN") == 1
    assert "Warm corridor light" in kf2 and "Held on the left of the lane" in kf2


def test_name_binding_never_fires_inside_longer_cast_name():
    sh = _shot(chars=("Keen", "Keen's Mum"))
    sh.performanceAssignment = "Keen's Mum kneels as Keen dives past."
    text, _ = E._inline_bindings(sh.performanceAssignment, sh, CFG)
    assert "Keen's Mum (@图2" in text and "Keen (@图3" in text
    assert ")'s Mum" not in text


def test_duration_bounds_enforced_by_schema():
    # 2026-07-21: ceiling raised 8->15 to accommodate multi-cut shots (paced_cuts/
    # rapid_cuts) per Seedance's own real multi-shot budget (10-15s for 2-3 cuts,
    # [ref:multishot-grammar]) — 12.0 now legitimately fits; 20.0 is the real over-cap case.
    with pytest.raises(Exception):
        _shot(dur=20.0)
    with pytest.raises(Exception):
        _shot(dur=2.0)


if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call(["python3", "-m", "pytest", __file__, "-q"]))


# ── THE SHOT-MODE VOCABULARY + SOURCE-MATERIAL PROOF (originally Julian's Option B +
# Anti-Guardrail Principle, 2026-07-23, proven on the then-promoted SH2A/SH2B split shots).
# GOLD BUILD UPDATE (2026-07-24): the split was re-merged in production (the canonical
# package holds S1.SH2 again, a hybrid_approved four-mode shot) and compile_shot_contract
# now emits the SOURCE-MATERIAL brief, never a mode-lean fireable prose brief — so these
# tests now prove (a) the real canonical shot compiles to the labelled source-material
# shape carrying its own physics AND dialogue facts, non-fireable by construction, and
# (b) the surviving mode-vocabulary machinery (_modes_dialogue_only/_quality_line) still
# selects vocabulary by REMOVING, exactly as the original split proof pinned.
def _real_canonical_shot(shot_id="S1.SH2"):
    import json as _json
    canon = _json.load(open(E.canonical_package_path(1, "Ep1")))
    fields = set(E.Shot.model_fields)
    chars = _json.load(open("config/characters.json"))
    scene = {"sceneName": canon.get("sceneName", "")}
    s = next(x for x in canon["shots"] if x["shotId"] == shot_id)
    shot = E.Shot(**{k: v for k, v in s.items() if k in fields})
    prompt, wc, _slots = E.compile_shot_contract(shot, scene, chars)
    return prompt, wc, shot


def test_real_canonical_shot_compiles_to_the_source_material_shape():
    """The real, live S1.SH2 (the re-merged hybrid) must compile to the labelled SOURCE-
    MATERIAL brief — every storyboard-approved fact category present, dialogue verbatim as
    material — and that brief must be REFUSED by the formula gate (never fireable)."""
    import cb_render as R
    prompt, wc, shot = _real_canonical_shot()
    assert prompt.startswith("SOURCE MATERIAL")
    for label in ("FELT INTENT", "OPENING ANCHOR", "CAMERA (storyboard-approved)",
                  "PERFORMANCE (approved physical performance)",
                  "DIALOGUE — THE AUDIO LAW", "HARD CONSTRAINTS", "DURATION:"):
        assert label in prompt, f"missing labelled fact: {label}"
    for ln in shot.dialogueLines:
        assert ln.exactText in prompt              # verbatim material, both lines
    with pytest.raises(R.Refused, match="THE FORMULA GATE"):
        R.check_formula_structure(prompt, shot.dialogueLines, refuse_prefix="REFUSED — test")


def test_source_brief_carries_both_physics_and_dialogue_facts_in_their_own_sections():
    """The materially-different guarantee, re-homed: the ONE source brief now separates the
    kinetic material (the gag's own physics chain, under GAG PHYSICS) from the vocal
    material (under THE VERBATIM LAW) — each labelled, neither displacing the other."""
    prompt, _wc, shot = _real_canonical_shot()
    low = prompt.lower()
    # kinetic facts from the shot's own physicalStaging, labelled
    assert "GAG PHYSICS" in prompt
    assert "compress" in low and "pollen" in low
    # vocal facts, labelled, never mixed into the physics lines
    dlg_idx = prompt.index("DIALOGUE — THE AUDIO LAW")
    assert "Do I look official?" in prompt[dlg_idx:]
    assert "Yes Fuzzby Officially nuts!" in prompt[dlg_idx:]


def test_dialogue_only_mode_removes_competing_language():
    """E._modes_dialogue_only: only a purely dialogue/emotional mode set flips the lean
    branch; absent modes (unmigrated shots) and hybrids keep today's exact behaviour —
    the surviving mode machinery still selects vocabulary by REMOVING."""
    _p, _wc, hybrid = _real_canonical_shot()
    assert not E._modes_dialogue_only(hybrid)      # 4-mode hybrid keeps the kinetic line
    assert "motion blur" in E._quality_line(hybrid)
    dialogue_only = hybrid.model_copy(update={
        "performanceModes": ["DIALOGUE_PERFORMANCE", "EMOTIONAL_ACTING"]})
    assert E._modes_dialogue_only(dialogue_only)
    assert "motion blur" not in E._quality_line(dialogue_only)   # competing language removed
    unmigrated = hybrid.model_copy(update={"performanceModes": []})
    assert not E._modes_dialogue_only(unmigrated)
    assert E._quality_line(unmigrated) == E.QUALITY_LINE   # no modes -> unchanged behaviour


def test_shot_density_rule_is_a_decision_point():
    """>2 modes without the Director's recorded decision refuses at handover; with
    hybrid_approved it passes — a decision point, never an accumulating blocker."""
    _p, _wc, base = _real_canonical_shot()
    assert base.modeDensityDecision == "hybrid_approved"   # the real shot records its decision
    three = base.model_copy(update={
        "performanceModes": ["KINETIC_ACTION", "PHYSICAL_COMEDY", "COMEDY_REACTION"],
        "modeDensityDecision": None})
    # the check lives inline in distil_shot; exercise its exact condition here
    assert len(three.performanceModes) > 2 and not three.modeDensityDecision
    approved = three.model_copy(update={"modeDensityDecision": "hybrid_approved"})
    assert approved.modeDensityDecision == "hybrid_approved"


# ══ THE FOUR-LEVEL MODEL: beat / camera shot / generation clip / editorial output ══
# (Julian's directive, 2026-07-25). Levels 2 and 3 were conflated — one Shot Card was
# always exactly one generation. composedOf is the reference form; these tests pin down
# that it resolves member cards WITHOUT redefining them, and that the 1:1 default is
# byte-identically unchanged for every package that does not use it.

def test_clip_defaults_to_itself_byte_identically():
    """No composedOf → the clip IS the card. The compiled brief must not shift by a byte."""
    sh = _shot()
    members, prov = E.resolve_clip_members(sh)
    assert prov == "self" and [m.shotId for m in members] == [sh.shotId]
    # siblings=None and siblings=[...] must produce the identical brief for a 1:1 clip
    a, _, _ = E.compile_shot_contract(sh, {}, CFG)
    b, _, _ = E.compile_shot_contract(sh, {}, CFG, siblings=[sh])
    assert a == b, "supplying siblings changed a self-contained clip's compiled brief"
    assert "MEMBER SHOT CARDS" not in a


def test_clip_references_member_cards_without_redefining_them():
    """The whole point: the member's OWN authored camera/first frame/performance reach the
    brief, cited by shotId — no prose restatement of them on the parent."""
    m1 = _shot(shot_id="1.B1.S2")
    m1.camera = "Tight two-shot, locked"
    m1.openingPose = "Zenny already settled on the petal"
    m1.performanceAssignment = "Zenny holds still; only her antennae move."
    m1.visualPayoff = "She does not blink"
    m1.endingBehaviour = "cut_on_action"
    m2 = _shot(shot_id="1.B1.S3")
    m2.camera = "Low push, ground level"
    m2.openingPose = "Fuzzby's shadow crossing the stem"
    parent = _shot(shot_id="1.B1.S1", cut_pace="paced_cuts",
                   composed_of=("1.B1.S3", "1.B1.S2"))   # deliberately NOT sorted order
    sibs = [parent, m1, m2]

    members, prov = E.resolve_clip_members(parent, sibs)
    assert prov == "composed"
    assert [m.shotId for m in members] == ["1.B1.S3", "1.B1.S2"], "authored order not held"

    brief, _, _ = E.compile_shot_contract(parent, {}, CFG, siblings=sibs)
    assert "MEMBER SHOT CARDS" in brief
    assert brief.index("[1.B1.S3]") < brief.index("[1.B1.S2]")
    for fragment in ("Low push, ground level", "Zenny already settled on the petal",
                     "only her antennae move", "cut_on_action"):
        assert fragment in brief, f"member card's own {fragment!r} never reached the clip"
    assert "INTERNAL CUTS" not in brief, "prose form must not also fire"


def test_clip_members_resolve_from_a_package_dict_too():
    """The canonical package on disk holds dicts, not typed Shots (the as_shot boundary)."""
    m = _shot(shot_id="1.B1.S2")
    parent = _shot(shot_id="1.B1.S1", cut_pace="paced_cuts", composed_of=("1.B1.S2",))
    pkg = {"shots": [parent.model_dump(), m.model_dump()]}
    members, prov = E.resolve_clip_members(parent, pkg)
    assert prov == "composed" and [x.shotId for x in members] == ["1.B1.S2"]


def test_unresolvable_members_raise_rather_than_silently_dropping():
    parent = _shot(shot_id="1.B1.S1", cut_pace="paced_cuts", composed_of=("1.B1.S9",))
    for siblings, why in ((None, "no siblings supplied"), ([parent], "ref not in scene")):
        try:
            E.resolve_clip_members(parent, siblings)
        except E.ClipMemberError:
            continue
        raise AssertionError(f"{why}: resolved silently instead of raising")
    # self-reference and nesting are both refused
    a = _shot(shot_id="1.B1.S1", cut_pace="paced_cuts", composed_of=("1.B1.S1",))
    try:
        E.resolve_clip_members(a, [a]); raise AssertionError("self-reference accepted")
    except E.ClipMemberError:
        pass
    inner = _shot(shot_id="1.B1.S2", cut_pace="paced_cuts", composed_of=("1.B1.S3",))
    outer = _shot(shot_id="1.B1.S1", cut_pace="paced_cuts", composed_of=("1.B1.S2",))
    try:
        E.resolve_clip_members(outer, [outer, inner, _shot(shot_id="1.B1.S3")])
        raise AssertionError("nested clip accepted")
    except E.ClipMemberError:
        pass


def test_clip_owner_identifies_a_member_card():
    m = _shot(shot_id="1.B1.S2")
    parent = _shot(shot_id="1.B1.S1", cut_pace="paced_cuts", composed_of=("1.B1.S2",))
    sibs = [parent, m]
    assert E.clip_owner_of("1.B1.S2", sibs) == "1.B1.S1"
    assert E.clip_owner_of("1.B1.S1", sibs) is None       # a clip owns itself, not "owned"
