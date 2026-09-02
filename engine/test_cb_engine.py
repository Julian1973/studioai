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
import inspect
import json
import pytest

import cb_engine as E


# ── fixtures ────────────────────────────────────────────────────────────────────────────
CFG = {"Fuzzby": {"sizeRank": 2, "avoid": "bee"}, "Zenny": {"sizeRank": 3, "avoid": "bee"},
       "Keen": {"sizeRank": 5, "species": "bear"},
       "Keen's Mum": {"sizeRank": 4, "species": "bear"},
       "Squeaky": {"species": "dolphin"}}

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
          lines=(), binding=None, staging=None, dur=6.0, marks_in=None, marks_out=None):
    return E.Shot(
        shotId=shot_id, beatCode="1.B1", durationSec=dur, purpose="the launch",
        performanceAssignment="Fuzzby rockets between blossoms, clips a stem, wobbles, recovers.",
        camera="Wide tracking, bee height", openingPose="Fuzzby mid-launch outside the flower",
        sourceType=source, sourceShotId=src_id, cutInMotivation=None if src_id is None else "matched action",
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


def test_declared_offscreen_speaker_is_audible_without_becoming_visible():
    d = _clean_design()
    d.shots[0].charactersInFrame = ["Zenny"]
    d.shots[0].offscreenSpeakers = ["Fuzzby"]
    d.shots[0].continuityIn = _state(["Zenny"])
    d.shots[0].continuityOut = _state(["Zenny"], marks=["pollen dust"])
    assert "SPEAKER_NOT_VISIBLE" not in _codes(E.validate_scene_design(d, BEATS, CFG))


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


def test_later_entrant_does_not_pollute_opening_continuity_cast():
    d = _clean_design()
    shot = d.shots[1]
    shot.openingCharactersInFrame = [shot.charactersInFrame[0]]
    shot.continuityIn.characters = shot.continuityIn.characters[:1]
    assert "CONTINUITY_CAST_INCOMPLETE" not in _codes(
        E.validate_scene_design(d, BEATS, CFG))


def test_keyframe_uses_opening_cast_and_positive_species_evidence_only():
    shot = _clean_design().shots[0]
    shot.charactersInFrame = ["Bo", "Keen", "Aida"]
    shot.openingCharactersInFrame = ["Bo", "Keen"]
    shot.openingPose = "Bo walks beside Keen on the forest path"
    cfg = {
        "Bo": {"sizeRank": 1, "size": "small squirrel child", "avoid": "bee wings"},
        "Keen": {"sizeRank": 2, "size": "young bear"},
        "Aida": {"sizeRank": 3, "size": "adult bear"},
    }
    prompt, _, slots = E.compile_keyframe_prompt(
        shot, {"sceneName": "Crystal Woods"}, cfg)
    assert "Bo (@图1, squirrel)" in prompt
    assert "Keen (@图2, bear)" in prompt
    assert "Aida" not in prompt
    assert slots == {"@图1": "Bo", "@图2": "Keen", "@图3": "scene plate"}


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


def test_packed_unit_preserves_each_big_comedy_beats_physical_staging():
    d = _clean_design()
    second = E.PhysicalStaging(
        staysVisible="The pollen mark and blossom remain visible through the tumble.",
        contactAndWeight="The blossom cups Fuzzby and stops his forward momentum.",
        payoffShape="The correction ends with Fuzzby held upside down.",
        prohibitedStaging=["Do not hide the blossom contact."],
    )
    d.shots[0].beatCodes = ["1.B1", "1.B2"]
    d.shots[0].physicalStaging = None
    d.shots[0].physicalStagings = [
        E.BeatPhysicalStaging(beatCode="1.B1", **STAGING.model_dump()),
        E.BeatPhysicalStaging(beatCode="1.B2", **second.model_dump()),
    ]
    beats = BEATS + [{
        "beatCode": "1.B2", "comedyMode": "BIG", "storyBeat": "The fix gets worse.",
        "cuts": [],
    }]

    report = E.validate_scene_design(d, beats, CFG)
    assert report["passed"], report["issues"]


def test_packed_unit_refuses_duplicate_big_comedy_staging_owners():
    d = _clean_design()
    d.shots[0].physicalStagings = [
        E.BeatPhysicalStaging(beatCode="1.B1", **STAGING.model_dump()),
        E.BeatPhysicalStaging(beatCode="1.B1", **STAGING.model_dump()),
    ]
    d.shots[0].physicalStaging = None
    assert "DUPLICATE_PHYSICAL_STAGING" in _codes(
        E.validate_scene_design(d, BEATS, CFG))


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
    d = _clean_design()
    for sh in d.shots:
        prompt, _, _ = E.compile_shot_contract(sh, {}, CFG)
        assert "nailed it" not in prompt.lower()
        assert "why are you humming" not in prompt.lower()
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


def test_option_d_internal_contract_preserved_provider_brief_lean():
    """Julian's Option D (2026-07-16): authored constraints and planning intent stay in the
    internal contract; the Seedance brief stays lean and never repeats them."""
    sh = _clean_design().shots[0]
    sh.prohibited = ["Do not let Zenny react broadly.", "Do not resolve the crash here."]
    line, prov = E.hard_constraints(sh, CFG)
    assert all(a in line for a in ("Do not let Zenny react broadly",
                                    "Do not resolve the crash here"))   # preserved internally
    brief, wc, _ = E.compile_shot_contract(sh, {}, CFG)
    assert "let Zenny react broadly" not in brief             # not repeated at the provider
    assert "Hard constraints:" not in brief
    assert "the pose itself" not in brief and sh.purpose not in brief  # planning stays internal
    assert wc == len(brief.split())
    # the brief carries exactly the Option-D sections
    assert E.OPENER_ANCHOR[:-1] in brief                      # exact opening anchor
    assert "Use @Audio1 as the only voice" in brief           # audio + mouth assignment
    assert "Preserve character identity and relative scale." in brief
    assert "screen sides" not in brief          # 2026-07-17: no longer a default on every shot
    # render-critical protection derived from the gag's own visibility contract, capped small
    assert "Keep Fuzzby's whole silhouette above the petals at all times." in brief


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


def test_long_direction_is_preserved_and_makes_no_llm_call(monkeypatch):
    import cb_llm
    def _boom(*a, **k):
        raise AssertionError("prompt length must never invoke an LLM rewrite")
    monkeypatch.setattr(cb_llm, "structured", _boom)
    sh = _clean_design().shots[0]
    sh.performanceAssignment = " ".join(["Fuzzby weaves between the tall blossoms"] * 60)
    prompt, word_count, _ = E.compile_shot_contract(sh, {}, CFG)
    assert word_count == len(prompt.split())
    assert sh.performanceAssignment in prompt


def test_long_physical_performance_passes_without_a_length_gate():
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
    assert report["passed"], report["issues"]
    prompt, wc, _ = E.compile_shot_contract(d.shots[0], {}, CFG)
    assert wc == len(prompt.split())


def test_long_brief_remains_compilable():
    d = _clean_design()
    d.shots[0].performanceAssignment = " ".join(
        ["Fuzzby weaves between the tall blossoms, wings beating hard, chest leading"] * 15)
    prompt, word_count, _ = E.compile_shot_contract(d.shots[0], {}, CFG)
    assert word_count == len(prompt.split())
    assert d.shots[0].performanceAssignment in prompt
    report = E.validate_scene_design(d, BEATS, CFG)
    codes = _codes(report)
    assert "SHOT_OVERBUDGET" not in codes
    assert "COMPILE_GUARD" not in codes


def test_explicit_seedance_25_packed_unit_preserves_long_form_direction():
    d = _clean_design()
    d.shots[0].beatCodes = ["1.B1"]
    d.shots[0].performanceAssignment = " ".join(
        ["Fuzzby weaves between the tall blossoms, wings beating hard, chest leading"] * 15)

    _prompt, words, _slots = E.compile_shot_contract(d.shots[0], {}, CFG)
    assert words == len(_prompt.split())
    report = E.validate_scene_design(d, BEATS, CFG)
    assert report["passed"], report["issues"]


def test_render_performance_assignment_may_carry_locked_dialogue():
    """Render performance may carry the locked line; keyframes remain dialogue-free."""
    d = _clean_design()
    d.shots[0].performanceAssignment = (
        'Fuzzby commits fully, chest leading into the recovery, and declares "Nailed it." '
        "as the whole beat turns on it.")
    prompt, _words, _slots = E.compile_shot_contract(d.shots[0], {}, CFG)
    assert "Nailed it." in prompt


def test_field_rejections_ignore_length_for_every_field():
    long_text = " ".join(["word"] * 200)
    assert E._field_rejections("performanceAssignment", long_text) == []
    assert E._field_rejections("visualPayoff", long_text) == []


def test_one_consistent_anchor_matching_style_rule():
    """Points 9 + Option D (2026-07-16): opener and relay both anchor style to their own @图1 —
    never 'Pixar-caliber', never a global 'squash-and-stretch'."""
    d = _clean_design()
    opener, _, _ = E.compile_shot_contract(d.shots[0], {}, CFG)
    relay, _, _ = E.compile_shot_contract(d.shots[1], {}, CFG)
    for p in (opener, relay):
        assert "Stylised feature-quality 3D CGI matching @图1." in p
        assert "Pixar-caliber" not in p and "squash-and-stretch" not in p
        assert "only for the set" in p                        # the plate has a declared job
    # the frozen keyframe IMAGE compiler is untouched by the rule
    kf, _, _ = E.compile_keyframe_prompt(d.shots[0], {}, CFG)
    assert "Stylised feature-quality 3D CGI with natural weight" in kf
    assert "Pixar-caliber" not in kf and "squash-and-stretch" not in kf


def test_concise_anchors_no_antihold_boilerplate():
    """Option D (2026-07-16): concise anchors; no compiled boilerplate about pose holding —
    the shot's own observable direction decides whether a pose continues."""
    assert E.OPENER_ANCHOR == "Begin exactly on @图1, the approved opening frame."
    assert E.RELAY_ANCHOR == ("Begin exactly on @图1, the approved final frame of the previous "
                               "shot, and continue the new action immediately.")
    relay, _, _ = E.compile_shot_contract(_clean_design().shots[1], {}, CFG)
    for banned in ("unnecessary hold", "Do not hold the previous pose", "restage"):
        assert banned not in relay


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
    assert "continuity in" not in kf.lower()
    assert "never composition or geography" in kf.lower()   # the plate's job line still prints
    assert wc == len(kf.split())


def test_keyframe_prompt_prints_continuity_paragraph_when_real_state_inherited():
    """The opposite case — genuinely inherited state (a real relay, not the sentinel)
    still prints normally, unaffected by the correction above."""
    shot = _clean_design().shots[0]
    real_state = E.ContinuityState(lighting="cooler storm light now reaching the petals",
                                    cameraSide="cooler storm light now reaching the petals",
                                    characters=[])
    shot = shot.model_copy(update={"continuityIn": real_state})
    kf, wc, _ = E.compile_keyframe_prompt(shot, {}, CFG)
    assert "continuity in: cooler storm light" in kf.lower()


def test_keyframe_prompt_is_reference_first_and_appearance_free():
    """2026-07-17 correction (Julian's Gate-B source-contract ruling, S1.SH1's rejected
    keyframe): the universal 'frame a touch wider... room to breathe' compiler nudge is
    REMOVED — it was a real, confirmed root cause of a compiled brief drifting to a wide
    scenic vista instead of the approved composition. Framing now comes solely from
    shot.openingPose (openingImage); the plate is explicitly barred from claiming
    composition or geography, only palette/materials/lighting."""
    kf, wc, _ = E.compile_keyframe_prompt(_clean_design().shots[0], {}, CFG)
    assert "wider" not in kf.lower()                  # the room-to-breathe law is GONE
    assert "never composition or geography" in kf.lower()   # the plate's job is explicitly scoped
    assert wc == len(kf.split())
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
    assert kf.count("Warm corridor light, Fuzzby already at speed") == 1
    # a genuinely distinct pair still states both
    sh2 = _shot(chars=("Fuzzby",))
    sh2.continuityIn = E.ContinuityState(
        lighting="Warm corridor light.", cameraSide="Held on the left of the lane.",
        characters=[E.CharacterState(character="Fuzzby", screenZone="frame-left", facing="right",
                                      pose="mid-hover", expression="proud",
                                      visibleMarks=[], heldProps=[])])
    kf2, wc2, _ = E.compile_keyframe_prompt(sh2, {}, CFG)
    assert "Warm corridor light" in kf2 and "Held on the left of the lane" in kf2


def test_name_binding_never_fires_inside_longer_cast_name():
    sh = _shot(chars=("Keen", "Keen's Mum"))
    sh.performanceAssignment = "Keen's Mum kneels as Keen dives past."
    text, _ = E._inline_bindings(sh.performanceAssignment, sh, CFG)
    assert "Keen's Mum (@图2" in text and "Keen (@图3" in text
    assert ")'s Mum" not in text


def test_cross_species_binding_uses_canonical_species_without_invented_size_comparison():
    sh = _shot(chars=("Keen", "Squeaky"))
    sh.openingPose = "Keen stands in the sailboat while Squeaky waits below the waterline."
    text, _ = E._inline_bindings(sh.openingPose, sh, CFG, start=1)
    assert "Keen (@图1, bear)" in text
    assert "Squeaky (@图2, dolphin)" in text
    assert "larger bear" not in text
    assert "smaller bear" not in text


def test_duration_bounds_enforced_by_schema():
    assert _shot(dur=30.0).durationSec == 30.0
    with pytest.raises(Exception):
        _shot(dur=31.0)
    with pytest.raises(Exception):
        _shot(dur=2.0)


def test_source_storyboard_record_carries_dependency_signature(tmp_path):
    """A generated package must be approvable without a stale-signature dead end."""
    path = tmp_path / "storyboard.json"
    signature = {"kind": "scene-storyboard-snapshot", "digest": "signed-storyboard"}
    path.write_text(json.dumps({"approvalState": "generated-pending-human-review",
                                "inputSignature": signature}))

    record = E._source_storyboard_record(path)

    assert record["inputSignature"] == signature
    assert record["approvalState"] == "generated-pending-human-review"
    assert record["sha256"] and record["md5"]


def test_storyboard_snapshot_signature_shape_matches_state_gate():
    source = inspect.getsource(E.compile_scene_package)
    assert '"beatPackageDigest": (d.get("contentSignature") or {}).get("digest")' in source
    assert '"sourceBeatIds": [b.get("sourceBeatId") for b in beats]' in source


if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call(["python3", "-m", "pytest", __file__, "-q"]))
