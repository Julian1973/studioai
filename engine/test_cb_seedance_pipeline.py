import pytest

import cb_prompt_lab
import cb_seedance_pipeline as S


def _image_ref(tag="@Image 1", subject="Hero"):
    return {
        "tag": tag,
        "subject": subject,
        "defines": "approved identity, proportions, materials, and clothing",
        "exclude": "the reference background, text labels, and unrelated objects",
    }


def _video_ref(tag="@Video 1", subject="Source Motion"):
    return {
        "tag": tag,
        "subject": subject,
        "defines": "approved motion, blocking, camera rhythm, and event order",
        "exclude": "the source identity, materials, and scene",
    }


def _stage(time, event="The hero crosses the room.", end="The hero stops by the window."):
    return {
        "time": time,
        "initial_state": "The hero begins in the preceding approved state.",
        "event": event,
        "end_state": end,
        "emotion_or_camera": "A restrained push lets the visible reaction register.",
    }


@pytest.mark.parametrize("task_type", S.SEEDANCE_TASK_TYPES)
def test_classifier_respects_every_explicit_task_type(task_type):
    result = S.classify_seedance_task({"type": task_type, "goal": "Make the shot."})
    assert result["type"] == task_type
    assert result["explicit"] is True


def test_classifier_uses_specific_inputs_before_generic_edit_words():
    result = S.classify_seedance_task({
        "goal": "Edit the look while rendering this blockout.",
        "blockout_kind": "coarse",
    })
    assert result["type"] == "blockout_render"


def test_asset_validator_enforces_hard_limits_and_keeps_recommendations_advisory():
    invalid = S.asset_validation_report({
        "images": [{}] * 31,
        "videos": [{"duration_seconds": 4}] * 8,
        "audio": [{"duration_seconds": 4}] * 8,
    })
    assert invalid["ok"] is False
    assert "Seedance 2.5 supports up to 30 images." in invalid["errors"]
    assert "Reference videos must not exceed 30 seconds combined." in invalid["errors"]
    assert "Reference audio must not exceed 30 seconds combined." in invalid["errors"]

    advisory = S.asset_validation_report({
        "images": [{"subject_count": 9}],
        "videos": [{"duration_seconds": 4, "subject_count": 6}],
        "audio": [{"duration_seconds": 11}],
    })
    assert advisory["ok"] is True
    assert len(advisory["warnings"]) >= 4


def test_reference_binding_is_named_scoped_and_excludes_leakage():
    line = S.format_reference_binding(_image_ref())
    assert line.startswith("@Image 1 defines <Hero>'s approved identity")
    assert "Do not use the reference background" in line


def test_timeline_rejects_overlap_gap_and_missing_end_state_at_model_boundary():
    overlap = [S.SeedanceStage.model_validate(_stage("0-6 seconds")),
               S.SeedanceStage.model_validate(_stage("5-10 seconds"))]
    assert "Stage 2 overlaps Stage 1." in S.timeline_validation_report(overlap, 10)["errors"]

    gap = [S.SeedanceStage.model_validate(_stage("0-4 seconds")),
           S.SeedanceStage.model_validate(_stage("5-10 seconds"))]
    assert "Stage 2 leaves a gap after Stage 1." in S.timeline_validation_report(gap, 10)["errors"]

    with pytest.raises(ValueError):
        S.SeedanceStage.model_validate({"time": "0-5 seconds", "event": "Action", "end_state": ""})


def test_reference_prompt_compiles_parameters_outside_the_provider_prompt():
    task = {
        "type": "reference_based_generation",
        "goal": "Generate a 15-second cinematic smartwatch ad in a rainy neon city.",
        "duration_seconds": 15,
        "aspect_ratio": "16:9",
        "resolution": "720p",
        "references": [_image_ref(subject="Smartwatch")],
        "assets": {"images": [{"subject": "Smartwatch"}]},
        "scene_style": "Realistic commercial cinematography with wet reflections.",
        "camera": "Begin low, orbit slowly, then push toward the crown.",
        "stages": [
            _stage("0-5 seconds", "The watch rests on wet glass.", "The unlit watch stays centered."),
            _stage("5-10 seconds", "The screen wakes during a slow orbit.", "The interface is fully lit."),
            _stage("10-15 seconds", "The camera pushes toward the crown.", "The premium crown detail holds."),
        ],
        "audio": "Natural rain and subtle interface beeps only, no music.",
        "consistency": ["Keep the watch structure, droplet count, scene layout, and light direction stable."],
    }
    builder = S.SeedancePromptBuilder(task)
    prompt = builder.build()
    preflight = builder.preflight()

    assert "15-second" not in prompt
    assert "16:9" not in prompt
    assert "720p" not in prompt
    assert preflight["requestSettings"] == {
        "durationSec": 15.0,
        "aspectRatio": "16:9",
        "resolution": "720p",
        "modelId": "fal-seedance-2.5",
    }
    assert preflight["zeroSpend"] is True
    assert preflight["providerCalled"] is False

    analysis = cb_prompt_lab.analyze_seedance_prompt_contract(
        prompt,
        task_mode="reference-to-video",
        reference_contract=[{"assetTag": "@Image 1", "role": "character_identity"}],
        duration_sec=15,
        stage_plan=[{}, {}, {}],
    )
    assert analysis["status"] == "ready"


def test_forbidden_list_is_task_specific_not_blanket_boilerplate():
    text_only = S.SeedancePromptBuilder({
        "type": "text_to_video",
        "goal": "A lantern rolls gently across a wooden table.",
        "duration_seconds": 6,
        "stages": [_stage("", "A lantern rolls gently across a wooden table.", "The lantern stops beside a cup.")],
        "audio": "Quiet room ambience.",
        "consistency": ["Keep the table, lantern and light direction stable."],
    }).build()

    assert "[Forbidden]" not in text_only
    assert "no subtitles" not in text_only
    assert "no morphing" not in text_only
    assert "no style drift" not in text_only

    referenced = S.SeedancePromptBuilder({
        "type": "reference_based_generation",
        "goal": "Animate the approved hero reaction.",
        "duration_seconds": 6,
        "references": [_image_ref("@Image 1", "Hero"), _image_ref("@Image 2", "Scene")],
        "assets": {"images": [{}, {}]},
        "stages": [_stage("", "The hero notices the open door.", "The hero remains by the table.")],
        "audio": "Natural ambience.",
        "consistency": ["Keep identity, scale, room geography and light stable."],
    }).build()

    assert "do not mix identities between references" in referenced
    assert "do not use reference backgrounds unless explicitly assigned" in referenced


def test_first_last_storyboard_and_blockout_templates_are_distinct():
    first_last = S.SeedancePromptBuilder({
        "type": "first_last_frame",
        "goal": "The hero crosses the studio and closes the display case.",
        "duration_seconds": 8,
        "references": [_image_ref("@Image 1"), _image_ref("@Image 2")],
        "assets": {"images": [{}, {}]},
        "continuous_action": "The hero crosses the studio and closes the display case.",
        "audio": "Natural footsteps and room ambience only, no music.",
        "consistency": ["Keep identity, case structure, studio layout, and camera direction stable."],
    }).build()
    assert "@Image 1 is the first frame" in first_last
    assert "@Image 2 is the last frame" in first_last

    storyboard = S.SeedancePromptBuilder({
        "type": "storyboard_grid",
        "goal": "Build the approved three-shot museum sequence.",
        "duration_seconds": 8,
        "references": [_image_ref("@Image 1", "Storyboard Grid")],
        "assets": {"images": [{}]},
        "stages": [_stage("", "A wide shot establishes the gallery.", "The guide reaches the display."),
                   _stage("", "A close-up reveals the object.", "The object holds in focus.")],
        "audio": "Quiet gallery ambience only, no music.",
        "consistency": ["Keep the guide, display, gallery axis, and light direction stable."],
    }).build()
    assert "provides the storyboard grid" in storyboard
    assert "Shot 2:" in storyboard

    blockout = S.SeedancePromptBuilder({
        "type": "blockout_render",
        "goal": "Render the guide pushing the display cart through the gallery.",
        "duration_seconds": 8,
        "references": [_video_ref(), _image_ref("@Image 1")],
        "assets": {"videos": [{"duration_seconds": 8}], "images": [{}]},
        "blockout_kind": "coarse",
        "blockout_mappings": ["The tall cylinder corresponds to <Guide>."],
        "audio": "Footsteps, wheel sounds, and gallery ambience only, no music.",
        "consistency": ["Keep the mapped subject count, path, gallery axis, and light stable."],
    }).build()
    assert "is a coarse blockout reference" in blockout
    assert "tall cylinder corresponds to <Guide>" in blockout


def test_edit_extension_and_transition_define_preservation_boundaries():
    edit = S.SeedancePromptBuilder({
        "type": "video_editing",
        "goal": "Change the jacket from blue to green.",
        "duration_seconds": 8,
        "references": [_video_ref()],
        "assets": {"videos": [{"duration_seconds": 8}]},
        "edit_scope": "Change only the jacket from seconds 2-6.",
        "preserve": ["Keep identity, motion, camera, dialogue, ambience, and timing unchanged."],
        "audio": "Preserve the source audio exactly; no new music.",
        "consistency": ["Keep all non-jacket pixels and timing relationships stable."],
    }).build()
    assert "sole editing master" in edit
    assert "[Edit Scope]" in edit

    extension = S.SeedancePromptBuilder({
        "type": "video_extension",
        "goal": "The paper airplane continues right and lands on the shelf.",
        "duration_seconds": 6,
        "references": [_video_ref()],
        "assets": {"videos": [{"duration_seconds": 8}]},
        "extension_direction": "forward",
        "audio": "Continue the room ambience and paper movement only, no music.",
        "consistency": ["Keep the plane, classroom, camera axis, light, and motion direction stable."],
    }).build()
    assert "first frame of the extended segment directly connects to the last frame" in extension
    assert "same continuous instance" in extension

    transition = S.SeedancePromptBuilder({
        "type": "seamless_transition",
        "goal": "Join the rainy street to the gallery.",
        "duration_seconds": 6,
        "references": [_video_ref("@Video 1"), _video_ref("@Video 2")],
        "assets": {"videos": [{"duration_seconds": 8}, {"duration_seconds": 8}]},
        "transition_trigger": "The red umbrella fills the lens.",
        "transition_transformation": "Its rim becomes the gallery skylight.",
        "arrival_state": "Arrive on the upward gallery composition and motion.",
        "audio_transition": "Rain fades into gallery footsteps.",
        "consistency": ["Keep both original clips unchanged."],
    }).build()
    assert "Connect them without modifying either source clip" in transition
    assert "[Arrival State]" in transition


def test_long_form_authoring_can_be_ready_while_provider_route_remains_blocked():
    task = {
        "type": "ultra_long_video",
        "goal": "Tell a one-minute emotional story in the workshop.",
        "duration_seconds": 60,
        "stages": [_stage("0:00-0:30"), _stage("0:30-1:00")],
        "audio": "Natural workshop ambience only, no music.",
        "consistency": ["Keep identity, clothing, workshop geography, props, and light stable."],
    }
    result = S.SeedancePromptBuilder(task).preflight()
    assert result["readyForPrompt"] is True
    assert result["readyForProvider"] is False
    assert "No enabled provider route" in result["providerQualification"]["reason"]


def test_seedance_25_reference_authoring_uses_live_fal_route():
    ready = S.SeedancePromptBuilder({
        "type": "reference_based_generation",
        "goal": "Animate the approved hero reaction.",
        "duration_seconds": 10,
        "references": [_image_ref()],
        "assets": {"images": [{}]},
        "stages": [_stage("0-10 seconds")],
        "audio": "Natural ambience and foley only, no music.",
        "consistency": ["Keep identity, scale, set geography, and lighting stable."],
    }).preflight()
    assert ready["readyForPrompt"] is True
    assert ready["readyForProvider"] is True
    assert ready["providerQualification"]["providerModelId"] == "fal-seedance-2.5"
    assert ready["providerQualification"]["provider"] == "fal"

    thirty = S.SeedancePromptBuilder({
        "type": "thirty_second_video",
        "goal": "Build a staged 30-second scene.",
        "duration_seconds": 30,
        "stages": [_stage("0-10 seconds"), _stage("10-20 seconds"), _stage("20-30 seconds")],
        "audio": "Natural ambience only, no music.",
        "consistency": ["Keep identity, geography, props, camera axis, and light stable."],
    }).preflight()
    assert thirty["readyForPrompt"] is True
    assert thirty["readyForProvider"] is False


def test_existing_approved_prompt_is_hash_preserved_by_preflight():
    task = {
        "type": "reference_based_generation",
        "goal": "Animate the approved reaction.",
        "duration_seconds": 8,
        "references": [_image_ref()],
        "assets": {"images": [{}]},
        "audio": "Natural ambience only, no music.",
        "consistency": ["Keep identity and scene geography stable."],
    }
    approved = "APPROVED EXACT PROMPT\nDo not rewrite this text."
    result = S.SeedancePromptBuilder(task).preflight(existing_prompt=approved)
    assert result["providerPrompt"] == approved
    assert result["approvedPromptPreserved"] is True


def test_retry_analyzer_repairs_the_smallest_defective_unit():
    local = S.analyze_retry(["unwanted BGM appeared", "character face changed"])
    assert local["action"] == "video_editing"
    assert local["fullEpisodeRegeneration"] is False

    timing = S.analyze_retry(["stage skipped", "timing was too fast"])
    assert timing["action"] == "regenerate_defective_segment"

    boundary = S.analyze_retry(["hard cut at transition"])
    assert boundary["action"] == "repair_boundary"

    prompt = S.build_retry_prompt("Original approved direction.", ["unwanted BGM appeared"])
    assert "Preserve every successful" in prompt
    assert "Human review is required" in prompt
