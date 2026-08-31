from pathlib import Path

import pytest

import cb_emission_conformance as C


def test_production_emitters_have_no_word_limit_contracts():
    root = Path(__file__).resolve().parent.parent
    production_files = [
        root / "engine" / "cb_departments.py",
        root / "engine" / "cb_render.py",
        root / "engine" / "cb_engine.py",
        root / "engine" / "cb_emission_standard.py",
        root / "cb-studio" / "app.html",
    ]
    forbidden = (
        "MAX_ANIMATION_PROVIDER_PROMPT_WORDS",
        "KEYFRAME_PROMPT_PRODUCTION_BUDGET_WORDS",
        "FIELD_OVERBUDGET",
        "hardWordBudget",
        "wordCountAdvisory",
        "Keep providerPrompt between",
        "WORD DISCIPLINE",
    )
    for path in production_files:
        source = path.read_text(encoding="utf-8")
        assert not [token for token in forbidden if token in source], path


def test_aaa_registry_has_exactly_sixteen_unique_versioned_checks():
    assert C.AAA_PREFLIGHT_VERSION == "aaa-part-8-v2.1"
    assert [number for number, _ in C.AAA_PREFLIGHT_CHECKS] == list(range(1, 17))
    assert len({code for _, code in C.AAA_PREFLIGHT_CHECKS}) == 16
    assert set(C.AAA_CONFORMANCE) == set(range(1, 17))
    assert all(set(paths) == {"keyframe", "render", "voice"}
               for paths in C.AAA_CONFORMANCE.values())
    assert all(status in {"IMPLEMENTED+TESTED", "OPEN"}
               for paths in C.AAA_CONFORMANCE.values() for status in paths.values())


def test_time_tiles_cover_the_entire_route_without_gaps():
    tiles = C.time_tiles([
        {"stageNumber": 1}, {"stageNumber": 2}, {"stageNumber": 3},
    ], 9)
    assert [(item["startSec"], item["endSec"]) for item in tiles] == [
        (0.0, 3.0), (3.0, 6.0), (6.0, 9.0)]


def test_audio_cues_reject_regions_outside_the_route():
    with pytest.raises(C.EmissionConformanceError, match="outside the approved"):
        C.dialogue_cues([
            {"speaker": "Fuzzby", "startSec": 8.0, "endSec": 10.0},
        ], duration_sec=9)


def test_audio_cues_accept_director_timing_shape():
    cues = C.dialogue_cues([
        {
            "speaker": "Keen",
            "startsAtSec": 2.1,
            "estimatedDurationSec": 3.2,
            "text": "Like you said... it is part of growing up.",
        },
    ], duration_sec=9)
    assert cues[0]["startSec"] == 2.1
    assert cues[0]["endSec"] == pytest.approx(5.3)


def test_dialogue_synthesis_allows_typographic_punctuation_variants():
    prompt = (
        "AUDIO-AUTHORITY: @Audio1 is the sole authority for voice identity, cadence, "
        "delivery, mouth timing and silence. No alternative performance is permitted. "
        "Listeners remain silent and closed-mouth. No narration; no extra words; "
        "no subtitles or captions. " + C.SINGLE_INSTANCE_DIALOGUE_LOCK + "\n"
        "Dialogue placement: Keen, small but brave: {Like you said... it's part of growing up.}"
    )
    result = C.validate_dialogue_synthesis(prompt, [{
        "speaker": "Keen",
        "text": "Like you said… it’s part of growing up.",
    }])
    assert result["ready"] is True


def test_dialogue_synthesis_refuses_a_second_generated_voice_contract():
    prompt = (
        "AUDIO-AUTHORITY: @Audio1 is the sole authority for voice identity, cadence, "
        "delivery, mouth timing and silence. No alternative performance is permitted. "
        "Listeners remain silent and closed-mouth. No narration; no extra words; "
        "no subtitles or captions. The rendered dialogue is a guide track.\n"
        "Spoken action: Keen: {No matter how hard you try.}"
    )
    result = C.validate_dialogue_synthesis(prompt, [{
        "speaker": "Keen", "text": "No matter how hard you try.",
    }])
    assert result["ready"] is False
    assert any("transcript only" in error for error in result["errors"])


def test_multi_character_instance_lock_is_exact_and_deduplicated():
    assert C.character_instance_lock(["Fuzzby", "Zenny", "fuzzby"]) == (
        "Exactly one Fuzzby and one Zenny throughout; no duplicates of either character.")
    assert C.character_instance_lock(["Fuzzby"]) == ""
    assert C.character_instance_lock(
        ["Fuzzby", "Zenny", "fuzzby"], medium="still") == (
        "Exactly one Fuzzby and one Zenny appear in this image.")
    with pytest.raises(ValueError, match="medium"):
        C.character_instance_lock(["Fuzzby", "Zenny"], medium="print")


def test_reference_slot_and_multi_angle_boilerplate_is_deterministic():
    assert C.reference_slot_stability_line([
        ("@图1", "opening frame"), ("@图2", "Zenny")]) == (
        "Project-stable slots: @图1=opening frame; @图2=Zenny. Never swap roles.")
    assert C.multi_angle_collapse_line("@图2", "Zenny") == (
        "@图2: all turnaround angles are one Zenny, not extra characters.")
    assert C.multi_angle_collapse_summary([
        ("@图1", "Zenny"), ("@图2", "Fuzzby")]) == (
        "Multi-angle collapse: @图1=one Zenny; @图2=one Fuzzby; views are angles, "
        "not extra characters.")


def test_emission_standard_accepts_relay_state_only_reference_role():
    import cb_emission_standard as S

    prompt = """[Multimodal Reference Layer]
@图1 is the previous shot's approved final frame. Use it only for carried character state, emotion, pose relationship, lighting continuity and the handoff fact: Keen and Mum remain close. Do not use it as the scene geography, camera framing, pier layout, boat-position or composition authority.
@图2 defines scene/layout/light only. Do not use characters or action from it.

[One-Sentence Summary]
Keen faces the water and tries to be brave.

[Global Settings]
Feature-quality stylized 3D CGI. Geography: the pier and boat come from the scene plate.

[Camera and Shot Plan]
Shot 1: Camera: Medium two-shot. Action: Keen looks at the sea and swallows. End state: Keen faces the water with Mum beside him.

[Audio]
No music. No watermark."""

    report = S.preflight(prompt, duration_sec=9, timing_beats=[])

    assert not any(
        item["rule"] == "reference-role"
        for item in report["findings"])


def test_dialogue_direction_requires_written_prose_and_hold_is_ruled():
    cue = {"speaker": "Performer", "exactText": "Now."}
    line = C.dialogue_placement_line(
        cue, direction="calm over covered fear", hold_after=False)
    assert line == "Spoken action: Performer, calm over covered fear: {Now.}"
    assert "hold" not in line.casefold()
    with pytest.raises(C.EmissionConformanceError, match="raw token"):
        C.dialogue_placement_line(cue, direction="exhales")
    with pytest.raises(C.EmissionConformanceError, match="raw token"):
        C.dialogue_placement_line(cue, direction="the approved")


def test_false_hold_flag_removes_specialist_pause_prose():
    cue = {"speaker": "Performer", "exactText": "Hello."}
    line = C.dialogue_placement_line(
        cue,
        direction=(
            "brightens into welcome; hold the delighted pose a full beat after the "
            "line ends before moving on"),
        hold_after=False)
    assert line == (
        "Spoken action: Performer, brightens into welcome: {Hello.}")
    assert "hold" not in line.casefold()


def test_true_hold_flag_emits_one_compiler_owned_hold():
    cue = {"speaker": "Performer", "exactText": "Goodbye."}
    line = C.dialogue_placement_line(
        cue,
        direction=(
            "softens; hold the expression a full beat after the line ends before turning"),
        hold_after=True)
    assert line == (
        "Spoken action: Performer, softens: {Goodbye.} "
        "The pose holds a full beat after the line ends.")
    assert line.casefold().count("hold") == 1


def test_r17_drops_superseded_action_before_world_first_replacement():
    action = (
        "A performer reacts to thunder. Before either character reacts, the light cools "
        "and every flower closes.")
    contract = ["The environment changes completely before either character reacts."]
    assert C.drop_superseded_action_prefix(action, contract) == (
        "Before either character reacts, the light cools and every flower closes.")
    assert C.drop_superseded_action_prefix(action, []) == action


def test_instance_lock_equivalence_is_character_agnostic():
    assert C.is_instance_lock_equivalent(
        "Exactly one Alpha and one Beta throughout; no duplicates or blended identities.",
        ["Alpha", "Beta"])
    assert not C.is_instance_lock_equivalent(
        "Keep Alpha and Beta on the same route.", ["Alpha", "Beta"])


def test_emission_length_is_diagnostic_only_and_never_reduces_score():
    import cb_emission_standard as S

    detailed_direction = " ".join(["Preserve this approved visible direction."] * 600)
    prompt = f"""image_1 defines the opening frame. Do not use its text.
Dialogue language: English.
Shot 1: Camera: hold the approved composition. Action: {detailed_direction}
{{We are ready.}} Hold the pose for a full beat after the line ends.
End state: the approved emotional beat is visibly complete.
No music."""

    report = S.preflight(prompt, duration_sec=30, timing_beats=[])

    assert len(prompt) > 2500
    assert report["score"] == 10.0
    assert report["verdict"] == "PASS"


def test_emission_accepts_seedance_nonverbal_music_sfx_policy():
    import cb_emission_standard as S

    prompt = """image_1 defines the opening frame. Do not use its text.
Dialogue language: English.
Shot 1: Camera: hold the approved composition. Action: Keen looks to Aida and speaks.
{Thank you.} Hold the pose for a full beat after the line ends.
End state: the approved emotional beat is visibly complete.
[AUDIO AND EXCLUSIONS]
No narration. No improvised or extra words. No extra voices. No subtitles, captions, text overlays, or watermark. No character redesign, no wardrobe changes, no duplicated cast members, and no mouth movement from silent listeners. Seedance 2.5 must provide instrumental music, ambience and non-verbal SFX that support the scene; do not add sung lyrics, vocal music, narration, or any additional spoken words."""

    report = S.preflight(prompt, duration_sec=15, timing_beats=[])

    assert report["score"] == 10.0
    assert report["verdict"] == "PASS"
    assert not any(item["rule"] == "length" for item in report["findings"])
