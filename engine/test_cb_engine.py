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
    d.shots[0].continuityIn.characters = d.shots[0].continuityIn.characters[:1]
    assert "CONTINUITY_CAST_INCOMPLETE" in _codes(E.validate_scene_design(d, BEATS, CFG))


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
    assert wc <= E.MAX_SHOT_PROMPT_WORDS                      # hard ceiling
    assert wc <= 170                                          # genuinely lean for a simple shot
    # the brief carries exactly the Option-D sections
    assert E.OPENER_ANCHOR[:-1] in brief                      # exact opening anchor
    assert "Use @Audio1 as the only voice" in brief           # audio + mouth assignment
    assert "Preserve character identity, relative scale and screen sides." in brief
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


def test_word_overflow_fails_loud_with_no_llm_call(monkeypatch):
    import cb_llm
    def _boom(*a, **k):
        raise AssertionError("an over-budget contract must FAIL, never auto-compress via LLM")
    monkeypatch.setattr(cb_llm, "structured", _boom)
    sh = _clean_design().shots[0]
    sh.performanceAssignment = " ".join(["Fuzzby weaves between the tall blossoms"] * 60)
    with pytest.raises(ValueError, match="hard ceiling"):
        E.compile_shot_contract(sh, {}, CFG)


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


def test_keyframe_prompt_is_anticipation_and_reference_first():
    kf, wc, _ = E.compile_keyframe_prompt(_clean_design().shots[0], {}, CFG)
    assert "anticipation" in kf.lower() and "never the payoff" in kf.lower()
    assert "wider" in kf.lower()                      # the room-to-breathe law
    assert wc <= E.MAX_KEYFRAME_PROMPT_WORDS
    # rule 5: the compiler's own fixed text never describes appearance
    for banned in ("yellow", "stripe", "spectacles", "glasses", "fur", "fuzzy"):
        assert banned not in kf.lower()


def test_name_binding_never_fires_inside_longer_cast_name():
    sh = _shot(chars=("Keen", "Keen's Mum"))
    sh.performanceAssignment = "Keen's Mum kneels as Keen dives past."
    text, _ = E._inline_bindings(sh.performanceAssignment, sh, CFG)
    assert "Keen's Mum (@图2" in text and "Keen (@图3" in text
    assert ")'s Mum" not in text


def test_duration_bounds_enforced_by_schema():
    with pytest.raises(Exception):
        _shot(dur=12.0)
    with pytest.raises(Exception):
        _shot(dur=2.0)


if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call(["python3", "-m", "pytest", __file__, "-q"]))
