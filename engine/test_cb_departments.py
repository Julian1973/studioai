"""Focused proofs for the live department workers (all zero-provider-call)."""
import hashlib
import json
from types import SimpleNamespace

import pytest

import cb_departments as D
import cb_render as R
import cb_safety


def test_animation_reference_contract_rebinds_props_and_location_in_upload_order():
    plan = [
        {"slot": "@图1", "role": "opening keyframe"},
        {"slot": "@图2", "role": "Keen"},
        {"slot": "@图3", "role": "prop:keen_sailboat"},
        {"slot": "@图4", "role": "prop:keen_sailboat_departure_state"},
        {"slot": "@图5", "role": "scene plate"},
    ]
    shot = {"charactersInFrame": ["Keen"], "dialogueLines": [{"speaker": "Keen"}]}

    contract = R._animation_reference_contract(plan, shot, "/tmp/voice.wav")

    assert [(item["assetTag"], item["role"]) for item in contract] == [
        ("@图1", "opening_frame"),
        ("@图2", "character_identity"),
        ("@图3", "prop"),
        ("@图4", "prop"),
        ("@图5", "location"),
        ("@Audio1", "audio"),
    ]
    assert "sailboat" in contract[2]["controls"]
    assert "departure state" in contract[3]["controls"]


def test_animation_compiler_never_reorders_a_sealed_contiguous_slot_map():
    references = [
        {"assetTag": "@图1", "role": "opening_frame", "controls": "the opening frame"},
        {"assetTag": "@图2", "role": "character_identity", "controls": "Keen identity"},
        {"assetTag": "@图3", "role": "prop", "controls": "the exact sailboat"},
        {"assetTag": "@图4", "role": "prop", "controls": "the packed cargo state"},
        {"assetTag": "@图5", "role": "location", "controls": "the open-sea scene"},
    ]

    ordered = D._render_reference_order(references)

    assert [(item["assetTag"], item["role"]) for item in ordered] == [
        ("@图1", "opening_frame"),
        ("@图2", "character_identity"),
        ("@图3", "prop"),
        ("@图4", "prop"),
        ("@图5", "location"),
    ]


def test_animation_compiler_suppresses_numbered_reference_prose_from_ownership():
    data = {
        "attributeOwnership": [
            "@图4 controls the old scene look only.",
            "The map belongs only to Keen.",
        ]
    }

    clean = D._approved_attribute_ownership(data)

    assert clean == ["The map belongs only to Keen."]


def test_seedance25_prompt_adapter_removes_legacy_controls_without_rewriting_action():
    source = (
        "4K ultra HD, 60fps, HDR, subject {1.2}, "
        "Consistency/Creativity: Consistency 80 / Creativity 20. "
        "High Quality + Cloth Simulation Optimization. "
        "Fuzzby loads the leaf with his weight, then recovers into a proud hold."
    )

    adapted = D.adapt_seedance25_prompt(source)

    assert "4K" not in adapted and "60fps" not in adapted and "HDR" not in adapted
    assert "{1.2}" not in adapted
    assert "Consistency/Creativity" not in adapted
    assert "Cloth Simulation Optimization" not in adapted
    assert "Fuzzby loads the leaf with his weight" in adapted
    assert "recovers into a proud hold" in adapted


def test_aerial_camera_contract_is_deterministic_compiler_boilerplate():
    aerial = SimpleNamespace(
        purpose="Squeaky aerial leap",
        causalAction="One dolphin leaps from water to air and back.",
        framingLensAndCamera="Follow beside the hull.")
    direction = SimpleNamespace(
        shotPlan=[aerial],
        model_dump=lambda: {"timingBeats": [{"type": "aerial", "count": 1}]})

    D.enforce_aerial_camera_contract(direction)

    assert aerial.framingLensAndCamera.endswith("Camera tracks the full arc.")


def test_signature_dive_is_typed_as_aerial_camera_ownership():
    aerial = SimpleNamespace(
        purpose="Squeaky's sunlit signature dive",
        causalAction="The dolphin breaches, performs a half-roll, and re-enters.",
        framingLensAndCamera="Low side view beside the moving hull.")
    direction = SimpleNamespace(
        shotPlan=[aerial],
        model_dump=lambda: {"timingBeats": [{"type": "aerial", "count": 1}]})

    D.enforce_aerial_camera_contract(direction)

    assert aerial.framingLensAndCamera.endswith("Camera tracks the full arc.")


def _locked():
    return [{"speaker": "FUZZBY", "exactText": "Nailed it."}]


def _voice_line(**overrides):
    values = {
        "speaker": "FUZZBY", "character": "FUZZBY", "exactDialogue": "Nailed it.",
        "performedText": "[nervous] NAILED... it.",
        "dramaticIntention": "sell control", "subtext": "the body disagrees",
        "cadenceAndBreath": "too bright", "timingAndBody": "after the rebound",
        "archetypeId": "false-triumph-button",
        "performanceQuestions": {
            "intention": "convince Zenny", "subtext": "hide the crash",
            "thoughtBefore": "hold the pose", "changeDuring": "breath becomes certainty",
            "operativeWords": ["Nailed"]},
        "physicalState": "wobbling hover",
        "emotionalState": {"entry": "winded", "exit": "proud"},
        "listener": "Zenny", "bodyVoiceRelationship": "voice covers the wobble",
        "previousText": "BIZZY-BIZZY-BIZZY...",
        "startsAtSec": 0.5, "estimatedDurationSec": 1.0,
        "pauseReasons": ["The ellipsis lets the impact breath catch up."],
        "tagPurposes": {"nervous": "Colours the false confidence."},
        "takeRecipes": [{"recipeId": "A", "label": "primary",
                         "performedText": "[nervous] NAILED... it.",
                         "primary": True, "takesCount": 3}],
    }
    values.update(overrides)
    return D.VoiceLineDirection(**values)


def test_every_studio_department_loads_a_real_runtime_skill_contract():
    people = D.roster()
    assert len(people) == 7
    assert all(p["loaded"] for p in people)
    assert {p["worker"] for p in people} >= {
        "Director", "Cinematographer / DP", "Voice Director",
        "Seedance Production Director", "Director Review / Continuity Supervisor",
        "Post Supervisor"}


def test_cinematography_preserves_canonical_cast_order_without_rejecting_reorder(monkeypatch):
    direction = D.CinematographyDirection(
        shotId="S1.SH2",
        audienceRead="The storm interrupts the warm aftermath.",
        composition="Fuzzby frame-left and Zenny frame-right.",
        lensAndCameraRelationship="Medium-wide at bee height.",
        lightingAndDepth="Warm light turns cool while geometry remains stable.",
        geography=["The corridor runs frame-left to frame-right."],
        openingFrameLayout={
            "referenceCharacter": "Fuzzby", "referenceHeightFraction": 0.3,
            "sameDepth": True,
            "placements": [
                {"character": "Zenny", "centerX": 0.7, "centerY": 0.5,
                 "depthPlane": 0, "facing": "frame-left", "pose": "steady hover"},
                {"character": "Fuzzby", "centerX": 0.3, "centerY": 0.5,
                 "depthPlane": 0, "facing": "frame-right", "pose": "wobbling hover"},
            ],
        },
        negativeSpace=["Keep the narrow sky gap visible."],
        providerPrompt="A complete provider-facing opening-frame direction for the storm turn.",
    )
    monkeypatch.setattr(D.cb_llm, "structured", lambda *_args, **_kwargs: direction)

    result = D.prepare_cinematography({
        "shot": {"charactersInFrame": ["Fuzzby", "Zenny"]},
    }, [])

    assert result.charactersInFrame == ["Fuzzby", "Zenny"]
    assert [item.character for item in result.openingFrameLayout.placements] == [
        "Fuzzby", "Zenny"]


def test_cinematography_allows_declared_later_entrant_outside_opening_frame(monkeypatch):
    direction = D.CinematographyDirection(
        shotId="3.B7.S1",
        audienceRead="Keen sails away before Squeaky interrupts the farewell.",
        composition="Keen aboard; Mum readable behind; clear water beside the hull.",
        lensAndCameraRelationship="Low trailing three-quarter view.",
        lightingAndDepth="Warm sun with clear departure depth.",
        geography=["The bow points frame-right toward open water."],
        openingFrameLayout={
            "referenceCharacter": "Keen", "referenceHeightFraction": 0.3,
            "sameDepth": False,
            "placements": [
                {"character": "Keen", "centerX": 0.65, "centerY": 0.5,
                 "depthPlane": 0, "facing": "frame-right", "pose": "sailing"},
                {"character": "Keen's Mum", "centerX": 0.2, "centerY": 0.45,
                 "depthPlane": 1, "facing": "toward Keen", "pose": "watching"},
            ],
        },
        negativeSpace=["Keep water beside the hull empty for Squeaky's later entrance."],
        providerPrompt="A complete provider-facing opening-frame departure direction.",
    )
    monkeypatch.setattr(D.cb_llm, "structured", lambda *_args, **_kwargs: direction)

    result = D.prepare_cinematography({
        "shot": {
            "charactersInFrame": ["Keen", "Keen's Mum", "Squeaky"],
            "openingCharactersInFrame": ["Keen", "Keen's Mum"],
        },
    }, [])

    assert result.charactersInFrame == ["Keen", "Keen's Mum"]
    assert [item.character for item in result.openingFrameLayout.placements] == [
        "Keen", "Keen's Mum"]


def test_voice_director_may_act_but_not_rewrite_locked_words():
    valid = D.VoiceDirection(
        shotId="S1.SH1", sceneIntention="cover the wobble",
        lines=[_voice_line()])
    assert D.validate_voice_direction(valid, _locked()) is valid

    changed = valid.model_copy(deep=True)
    changed.lines[0].performedText = "[nervous] Totally nailed it."
    with pytest.raises(RuntimeError, match="added, dropped or changed words"):
        D.validate_voice_direction(changed, _locked())

    invented = valid.model_copy(deep=True)
    invented.lines[0].archetypeId = "fuzzby-invented-archetype"
    with pytest.raises(RuntimeError, match="selected unregistered archetype"):
        D.validate_voice_direction(invented, _locked())

    missing_take_tag_purpose = valid.model_copy(deep=True)
    missing_take_tag_purpose.lines[0].takeRecipes.append(
        D.VoiceTakeRecipe(
            recipeId="B", label="alternate", performedText="[casual] Nailed it.",
            takesCount=2))
    repaired = D.validate_voice_direction(missing_take_tag_purpose, _locked())
    purposes = {item.tag: item.purpose for item in repaired.lines[0].tagPurposes}
    assert "casual" in purposes
    assert purposes["casual"]


def test_voice_direction_uses_openai_strict_tag_purpose_rows():
    from openai.lib._pydantic import to_strict_json_schema

    direction = D.VoiceDirection(
        shotId="S1.SH1", sceneIntention="cover the wobble", lines=[_voice_line()])
    assert direction.lines[0].tagPurposes[0].tag == "nervous"
    schema = to_strict_json_schema(D.VoiceDirection)
    field = schema["$defs"]["VoiceLineDirection"]["properties"]["tagPurposes"]
    assert field["type"] == "array"
    assert field["items"]["$ref"] == "#/$defs/VoiceTagPurpose"
    assert schema["$defs"]["VoiceTagPurpose"]["additionalProperties"] is False


def test_prepare_voice_loads_the_skill_and_stops_at_structured_candidate(monkeypatch):
    seen = {}

    def fake(system, user, schema, **kwargs):
        seen["system"] = system
        seen["user"] = user
        return schema(
            shotId="S1.SH1", sceneIntention="cover the wobble",
            lines=[_voice_line(performedText="[nervous] Nailed it.")])

    monkeypatch.setattr(D.cb_llm, "structured", fake)
    out = D.prepare_voice({"shotId": "S1.SH1"}, _locked(), log=lambda *a, **k: None)
    assert out.lines[0].performedText == "[nervous] Nailed it."
    assert "Runtime worker contract — Voice Director" in seen["system"]
    assert "REGISTERED VOICE ARCHETYPES" in seen["user"]
    assert "false-triumph-button" in seen["user"]
    assert "every bracketed audio tag" in seen["user"]


def test_animation_provider_shell_enforces_audio_lock_and_continuity_contract():
    shot = {
        "dialogueLines": [
            {"speaker": "Fuzzby", "exactText": "Nailed it."},
            {"speaker": "Zenny", "exactText": "Officially nuts!"},
        ]
    }
    prompt = (
        "AUDIO-LOCK: incomplete\n\n"
        "[One-Sentence Summary]\nFuzzby says Nailed it. while Zenny answers "
        "Officially nuts!\n\n[Audio]\nUse the approved voice track."
    )

    compiled = D._apply_animation_provider_shell(prompt, shot)

    assert compiled.startswith("AUDIO-AUTHORITY: @Audio1 is the sole authority")
    assert "listeners remain silent and closed-mouth" in compiled
    assert "[AUDIO AND EXCLUSIONS]" in compiled
    assert "No improvised or extra words" in compiled
    assert "no duplicated cast members" in compiled
    assert "Seedance may generate non-verbal music, ambience and SFX" in compiled
    assert "Spoken action: Fuzzby: {Nailed it.}" in compiled
    assert "Spoken action: Zenny: {Officially nuts!}" in compiled
    assert "@Audio1 remains the sole English dialogue and performance authority." in compiled
    assert compiled.index("[Global Supplement]") < compiled.index("[Audio]")
    for term in ("identity", "character count", "prop ownership", "camera axis",
                 "lighting continuity", "sound relationships"):
        assert term in compiled


def test_animation_provider_shell_replaces_an_incomplete_supplement():
    prompt = (
        "[One-Sentence Summary]\nFuzzby flies.\n\n"
        "[Global Supplement]\nKeep the flowers pretty.\n\n"
        "[Audio]\nUse natural foley."
    )

    compiled = D._apply_animation_provider_shell(prompt, {"dialogueLines": []})

    assert compiled.count("[Global Supplement]") == 1
    assert "Keep the flowers pretty." not in compiled
    assert compiled.index("[Global Supplement]") < compiled.index("[Audio]")
    assert "prop ownership" in compiled


def test_animation_provider_shell_rebuilds_reference_layer_one_asset_per_line():
    prompt = (
        "[Multimodal Reference Layer]\nUse all images as references.\n\n"
        "[One-Sentence Summary]\nFuzzby flies.\n\n"
        "[Audio]\nNatural ambience and foley."
    )
    references = [
        {"assetTag": "@Image1", "role": "opening_frame",
         "controls": "the approved opening composition", "scope": "continuity"},
        {"assetTag": "@Image2", "role": "character_identity",
         "controls": "Fuzzby's exact identity and proportions", "scope": "canon"},
    ]

    compiled = D._apply_animation_provider_shell(
        prompt, {"dialogueLines": []}, references)

    assert "Use all images as references." not in compiled
    assert "@Image1 defines only the approved opening composition." in compiled
    assert "@Image2 defines exactly one Fuzzby identity/scale only;" in compiled
    assert "exclude background, pose, props and scene" in compiled


def test_relay_opening_frame_contract_overrides_stale_first_frame_wording():
    shot = {
        "shotId": "3.B2.S1",
        "sourceType": "relay",
        "sourceShotId": "3.B1.S1",
        "charactersInFrame": ["Keen", "Keen's Mum"],
        "durationSec": 9,
        "dialogueLines": [],
    }
    direction = D.AnimationDirection(
        shotId="3.B2.S1",
        durationSec=9,
        taskMode="reference-to-video",
        pacingMode="storyline",
        generationGoal="Keen faces the water and tries to sound brave.",
        deliveryPlan="The handoff carries emotion while the scene plate owns geography.",
        creativeTranslation={
            "interpretation": {
                "jokeOrAche": "A small child borrows grown-up courage.",
                "mechanism": "The sea scale makes his bravery visible as effort.",
                "statusBefore": "close to Mum",
                "statusAfter": "braced toward the water",
                "audienceProgression": ["safe", "small", "brave"],
                "emotionalHeart": "Mum sees him trying.",
            },
            "gagClocks": [],
            "generationDesign": {
                "packagingDecision": "single-unit",
                "completeGagArcCount": 0,
                "densityJudgement": "one emotional turn",
                "splitOrNonSplitRationale": "single short unit",
                "handoffState": "Keen faces the open water with Mum beside him.",
            },
        },
        dramaticBeat="Keen looks out at the water.",
        audienceBefore="Keen is safe beside Mum.",
        audienceAfter="Keen is trying to leave.",
        beatOwner="Keen",
        performanceFreedom="Seedance may choose small breathing and eye details.",
        performanceArc="Keen swallows fear into a brave posture.",
        physicalCauseAndEffect="The sea fills the frame, so Keen has to steady himself.",
        cameraBehaviour="Child-height medium two-shot.",
        timingAndRhythm="Slow enough for the swallow to read.",
        landingBreath="Hold the braced expression.",
        directionDensity="guided",
        shotPlan=[{
            "shotNumber": 1,
            "purpose": "Bravery against the sea.",
            "framingLensAndCamera": "Medium two-shot at child eye height.",
            "causalAction": "Keen looks from the boat toward the water and swallows.",
            "observablePerformance": "Mum remains still beside him.",
            "compositionLightAndMaterials": "Warm pier light and open water.",
            "landingImage": "Keen faces the open water with Mum beside him.",
        }],
        timingBeats=[{"type": "reaction", "count": 1, "source": "swallow"}],
        stagePlan=[{
            "stageNumber": 1,
            "beatIds": ["3.B2"],
            "purpose": "Keen tries to be brave.",
            "initialOrCarriedState": "Keen and Mum carry the previous shoreline closeness.",
            "cause": "The open water is suddenly large in front of Keen.",
            "primaryEvent": "Keen looks out, swallows, and tries to steady himself.",
            "observableEndState": "Keen faces the open water with Mum beside him.",
            "emotionOrCameraAnalysis": "The hold lets the effort read.",
        }],
        geography=["The scene plate owns pier, boat, shoreline and water geography."],
        referenceContract=[
            {
                "assetTag": "@图1",
                "role": "opening_frame",
                "controls": "Approved opening composition, character positions, camera proximity, and carried shoreline/boat state for the relay start.",
                "scope": "continuity",
            },
            {
                "assetTag": "@图2",
                "role": "location",
                "controls": "Pier, boat, shoreline and open water.",
                "scope": "episode",
            },
        ],
        openingCarriedState="Keen and Mum carry the previous close emotional state.",
        consistencyContract=["Keen has bare wrists."],
        audioContract="No dialogue.",
        continuityFinish="Keen faces the open water with Mum beside him.",
        providerPrompt="Temporary provider prompt long enough for typed validation.",
    )

    compiled = D.compile_animation_provider_prompt(shot, direction)

    assert ("@图1 is the first frame and the previous shot's approved final frame."
            in compiled)
    assert "Use it only for carried character state" in compiled
    assert "Do not use it as the scene geography" in compiled
    assert "camera framing" in compiled
    assert "environment layout" in compiled
    assert "pier layout" not in compiled
    assert "boat-position" not in compiled
    assert compiled.count("图1 is the first frame") == 1
    assert "It defines opening composition and state" not in compiled


def test_prepare_direction_archives_a_stale_candidate_before_replacing_it(
        monkeypatch, tmp_path):
    pkg = {"episode": "EpT", "sceneNumber": "1", "revision": 2,
           "validation": {"passed": True}, "shots": [], "continuityLedger": []}
    record = {"approved": None, "candidate": None, "history": [],
              "departmentWork": {"look": {
                  "approved": None,
                  "candidate": {"output": {"providerPrompt": "stale prompt"},
                                "inputSignature": {"stale": True}},
                  "history": [],
              }}}

    class LookResult:
        def model_dump(self):
            return {"providerPrompt": "fresh prompt"}

    monkeypatch.setattr(R, "_require_show_adapter", lambda: None)
    monkeypatch.setattr(R, "load_pkg", lambda *_args, **_kwargs: (pkg, tmp_path / "pkg.json"))
    monkeypatch.setattr(R, "_require_valid", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(R, "_require_current_lineage", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(R, "_scene_context", lambda *_args, **_kwargs: {"scene": "1"})
    monkeypatch.setattr(R, "_load_scenelook_rec", lambda *_args, **_kwargs: record)
    monkeypatch.setattr(R, "_save_scenelook_rec", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(R, "_save", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(R.cb_departments, "prepare_look",
                        lambda *_args, **_kwargs: LookResult())
    monkeypatch.setattr(cb_safety.cb_canon, "load_policy", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        cb_safety.cb_canon, "require_locked",
        lambda *_args, **_kwargs: {"profileDigests": {"look": "canon-look"}})

    replacement = R.prepare_department("1", "look", episode="EpT", log=lambda *_: None)
    work = record["departmentWork"]["look"]

    assert replacement["output"]["providerPrompt"] == "fresh prompt"
    assert work["history"][0]["outcome"] == "invalidated"
    assert work["history"][0]["output"]["providerPrompt"] == "stale prompt"
    assert work["candidate"] is replacement


def test_seedance_director_returns_shot_plan_and_separate_reference_contract(monkeypatch):
    seen = {}

    def fake(system, user, schema, **kwargs):
        seen["system"] = system
        seen["user"] = user
        return schema(
            shotId="S1.SH1",
            durationSec=8,
            taskMode="reference-to-video",
            pacingMode="storyline",
            generationGoal="Generate Fuzzby's brave recovery after the deck shifts.",
            deliveryPlan="The planted-paw cause, restrained push and delayed flinch turn confidence into affection.",
            creativeTranslation=D.CreativeTranslationDirection(
                interpretation=D.DirectorInterpretationDirection(
                    jokeOrAche="Confidence is contradicted by the body.",
                    mechanism="The evidence arrives after the boast.",
                    statusBefore="Fuzzby claims control.", statusAfter="The deck exposes him.",
                    audienceProgression=["anticipation", "impact", "affection"],
                    emotionalHeart="His recovery matters more than perfection."),
                gagClocks=[],
                generationDesign=D.GenerationDesignDirection(
                    packagingDecision="single-unit", completeGagArcCount=0,
                    densityJudgement="One compact physical turn.",
                    splitOrNonSplitRationale="The cause and reaction belong together.",
                    handoffState="He holds a readable off-balance silhouette.")),
            dramaticBeat="Fuzzby performs confidence while the wobble exposes him.",
            audienceBefore="Amused anticipation.",
            audienceAfter="A laugh with affection.",
            beatOwner="Fuzzby",
            performanceFreedom="Seedance may discover the micro-reaction, overlap and recovery cadence.",
            performanceArc="Bright control tightens into a tiny private flinch.",
            physicalCauseAndEffect="His planted paw shifts the loose plank, causing the wobble.",
            cameraBehaviour="A restrained 40mm push reveals the instability.",
            timingAndRhythm="Hold, wobble, reaction, clean landing.",
            landingBreath="Let the recovered pose register before handing off.",
            directionDensity="guided",
            precisionReasons=[],
            shotPlan=[D.InternalShotDirection(
                shotNumber=1, purpose="Reveal the false confidence",
                framingLensAndCamera="Medium 40mm, slow motivated push",
                causalAction="His paw loads the plank and the deck kicks back",
                observablePerformance="His smile holds as his eyes flick down",
                compositionLightAndMaterials="Layered deck depth, warm rim on tactile fur",
                landingImage="He settles in a readable off-balance silhouette")],
            stagePlan=[D.SeedanceStageDirection(
                stageNumber=1, beatIds=["1.B1"], purpose="Expose the false confidence",
                initialOrCarriedState="Fuzzby holds the approved opening pose.",
                cause="His planted paw loads the loose plank.",
                primaryEvent="His planted paw loads the plank and the deck kicks back.",
                observableEndState="He holds a readable off-balance silhouette.",
                emotionOrCameraAnalysis="The restrained push lets the private flinch land.")],
            referenceContract=[D.ReferenceDirection(
                assetTag="@Image1", role="opening_frame",
                controls="Exact opening state and composition", scope="continuity")],
            geography=["The deck runs frame-left to frame-right; the camera stays south."],
            consistencyContract=["Keep Fuzzby's identity, scale and deck axis stable."],
            audioContract="No dialogue; preserve the deck creak and room ambience.",
            continuityFinish="End on the approved handoff silhouette.",
            surgicalSafeguards=["Preserve relative scale"],
            providerPrompt=(
                "[Multimodal Reference Layer]\n"
                "@Image1 only defines the exact first-frame composition.\n"
                "[One-Sentence Summary]\nGenerate Fuzzby's brave recovery after the deck shifts.\n"
                "[Global Settings]\nWarm tactile deck; restrained 40mm push; no subtitles.\n"
                "[Timestamp Script Storyboard]\nStage 1: [Expose the false confidence]\n"
                "Initial state: Fuzzby holds the approved opening pose.\n"
                "Action/Expression: his planted paw loads the plank and the deck kicks back as "
                "the 40mm camera makes a restrained push.\nEnd state: his smile holds while "
                "his eyes flick down in a readable off-balance silhouette.\n"
                "Emotion/Camera Analysis: the push lets the private flinch land.\n"
                "[Global Supplement]\nKeep identity, scale, deck axis and warm rim light.\n"
                "[Audio]\nNo dialogue; preserve the deck creak and room ambience."))

    monkeypatch.setattr(D.cb_llm, "structured", fake)
    story_lock_args = {}
    real_story_lock = D.animation_story_lock_report

    def capture_story_lock(shot, prompt, stage_plan=None, shot_plan=None):
        story_lock_args["shotPlan"] = shot_plan
        return real_story_lock(shot, prompt, stage_plan, shot_plan)

    monkeypatch.setattr(D, "animation_story_lock_report", capture_story_lock)
    out = D.prepare_animation(
        {"shot": {"shotId": "S1.SH1", "durationSec": 8,
                  "storyboardStagePlanApproved": [{
                      "stageNumber": 1, "beatIds": ["1.B1"],
                      "primaryEvent": "His planted paw loads the plank and the deck kicks back.",
                      "observableEndState": "He holds a readable off-balance silhouette.",
                  }]},
         "referenceSlots": {"@Image1": "opening frame"}},
        ["opening.png"], log=lambda *a, **k: None)
    assert len(out.shotPlan) == 1
    assert len(out.stagePlan) == 1
    assert out.pacingMode == "storyline"
    compiled = D.compile_animation_provider_prompt(
        {"shotId": "S1.SH1", "durationSec": 8, "dialogueLines": []}, out)
    assert "[Camera and Shot Plan]" in compiled
    assert "Phase 1: Camera: Medium 40mm, slow motivated push" in compiled
    assert "Action: His paw loads the plank and the deck kicks back" in compiled
    assert "Emotion/Camera Analysis:" not in compiled
    assert "Stage 1: 0-8s" not in compiled
    assert "Audio cues:" not in compiled
    assert out.durationSec == 8
    assert story_lock_args["shotPlan"] == out.shotPlan
    assert out.referenceContract[0].assetTag == "@Image1"
    assert "Runtime worker contract — Seedance Production Director" in seen["system"]
    assert "Emit every scripted line exactly once inside the stage that owns it" in seen["user"]
    assert "[Multimodal Reference Layer]" in seen["user"]
    assert "Stage N: 0-4s [Purpose]" in seen["user"]


def test_animation_story_lock_requires_every_approved_visual_event():
    shot = {"storyboardStagePlanApproved": [{
        "stageNumber": 1,
        "beatIds": ["1.B1"],
        "primaryEvent": "Fuzzby hits the leaf, says \u201cNailed it.\u201d, and rebounds upright.",
        "observableEndState": "Fuzzby hovers upright beside the recoiling leaf.",
    }]}
    locked = D.animation_locked_visual_events(shot)
    assert locked[0]["primaryEvent"] == "Fuzzby hits the leaf, and rebounds upright."

    report = D.animation_story_lock_report(
        shot,
        "Action/Expression: Fuzzby hits the leaf, and rebounds upright.",
        [{
            "primaryEvent": "Fuzzby hits the leaf, and rebounds upright.",
            "observableEndState": "Fuzzby hovers upright beside the recoiling leaf.",
        }],
    )
    assert report["ready"] is True

    missing = D.animation_story_lock_report(shot, "Fuzzby talks beside a flower.")
    assert missing["ready"] is False
    assert "approved visual event is absent" in missing["errors"][0]

    decomposed = D.animation_story_lock_report(
        shot,
        "Shot 1: Action: Fuzzby hits the leaf. End state: the leaf is loaded. "
        "Shot 2: Action: The leaf rebounds him upright. End state: Fuzzby hovers.",
        [{
            "primaryEvent": "Fuzzby hits the leaf, and rebounds upright.",
            "observableEndState": "Fuzzby hovers upright beside the recoiling leaf.",
        }],
        [
            {"causalAction": "Fuzzby hits the leaf."},
            {"causalAction": "The leaf rebounds him upright."},
        ],
    )
    assert decomposed["ready"] is True


def test_creative_translation_preserves_approved_gag_clock_and_provider_action():
    approved = {
        "beatCode": "1.B1", "mode": "BIG",
        "setup": "Fuzzby enters too fast for the flower corridor.",
        "disruption": "The bent leaf snaps him back into an upright hover.",
        "hold": "The wobbling proud recovery remains readable.",
        "button": "His recovery line claims success while his body disagrees.",
    }
    provider_action = (
        "Fuzzby compresses the leaf, rebounds upright, and holds his wobbling proud pose "
        "while Zenny remains still enough for the contrast to register.")
    direction = {
        "providerPrompt": (
            "Action/Expression: " + provider_action + " Hold: 2.2s — "
            + approved["hold"]),
        "creativeTranslation": {
            "gagClocks": [{
                "beatCode": "1.B1", "mode": "BIG", "setup": approved["setup"],
                "anticipation": "The leaf bends visibly before release.",
                "impact": approved["disruption"],
                "reaction": "Zenny gives one restrained look.",
                "recoveryHold": approved["hold"], "recoveryHoldSec": 2.2,
                "button": approved["button"], "providerAction": provider_action,
            }],
            "generationDesign": {
                "completeGagArcCount": 1,
                "handoffState": "Fuzzby hovers upright beside the leaf.",
            },
        },
    }
    shot = {
        "comedyContractsApproved": [approved],
        "visualPayoff": "Fuzzby hovers upright beside the leaf.",
        "dialogueLines": [{"exactText": "Nailed it."}],
    }
    assert D.creative_translation_report(shot, direction)["ready"] is True

    weakened = {**direction, "providerPrompt": "Fuzzby flies through the meadow."}
    report = D.creative_translation_report(shot, weakened)
    assert report["ready"] is False
    assert "providerAction is absent" in report["errors"][0]


def test_big_gag_requires_numeric_two_second_landing():
    common = {
        "beatCode": "1.B1", "mode": "BIG", "setup": "Fuzzby enters too fast.",
        "anticipation": "The leaf bends.", "impact": "The leaf throws him upright.",
        "reaction": "Zenny watches.", "recoveryHold": "Hold the proud wobble.",
        "button": "His body disproves the boast.",
        "providerAction": "Fuzzby rebounds upright and holds the proud wobble.",
    }
    with pytest.raises(ValueError, match="BIG gag hold < 2.0s"):
        D.GagClockDirection(**common, recoveryHoldSec=1.0)
    with pytest.raises(ValueError, match="recoveryHoldSec"):
        D.GagClockDirection(**common)
    assert D.GagClockDirection(**common, recoveryHoldSec=2.2).recoveryHoldSec == 2.2


def test_motion_vocabulary_blocks_out_of_character_verbs():
    direction = {
        "shotId": "S1.SH1A", "durationSec": 9,
        "generationGoal": "Fuzzby converts a crash into false triumph.",
        "deliveryPlan": "Keep the crash causal and the landing readable.",
        "creativeTranslation": {
            "interpretation": {
                "jokeOrAche": "His body contradicts him.", "mechanism": "Physical evidence.",
                "statusBefore": "Confident.", "statusAfter": "Exposed.",
                "audienceProgression": ["expect", "see", "laugh"],
                "emotionalHeart": "The failure stays affectionate.",
            },
            "gagClocks": [],
            "generationDesign": {
                "packagingDecision": "single-unit", "completeGagArcCount": 0,
                "densityJudgement": "One event.",
                "splitOrNonSplitRationale": "One causal action.",
                "handoffState": "Fuzzby holds upright.",
            },
        },
        "dramaticBeat": "False triumph.", "audienceBefore": "Expectation.",
        "audienceAfter": "Affection.", "beatOwner": "Fuzzby",
        "performanceFreedom": "Secondary motion remains free.",
        "performanceArc": "Confidence becomes wobble.",
        "physicalCauseAndEffect": "The leaf throws him upright.",
        "cameraBehaviour": "Bee-height track.", "timingAndRhythm": "Chase then hold.",
        "landingBreath": "The pose reads.", "directionDensity": "guided",
        "shotPlan": [{
            "shotNumber": 1, "purpose": "Land the contradiction.",
            "framingLensAndCamera": "Bee-height medium.",
            "causalAction": "The leaf recoils.", "observablePerformance": "He wobbles.",
            "compositionLightAndMaterials": "Warm flowers.",
            "landingImage": "He holds upright.",
        }],
        "stagePlan": [{
            "stageNumber": 1, "beatIds": ["1.B1"], "purpose": "False triumph.",
            "initialOrCarriedState": "The chase is moving.", "cause": "Too much speed.",
            "primaryEvent": "Fuzzby glides into the flower corridor.",
            "observableEndState": "Fuzzby holds upright.",
            "emotionOrCameraAnalysis": "The contradiction reads.",
        }],
        "geography": ["The corridor runs frame-left to frame-right."],
        "consistencyContract": ["Keep identity and geography stable."],
        "audioContract": "No dialogue; no music.",
        "continuityFinish": "Fuzzby holds upright.",
        "providerPrompt": "A sufficiently complete placeholder provider prompt for validation.",
    }
    with pytest.raises(ValueError, match="Fuzzby cannot 'glides'"):
        D.AnimationDirection.model_validate(direction)

    direction["stagePlan"][0]["primaryEvent"] = (
        "Fuzzby barrels through the flower corridor."
    )
    direction["motionVocabulary"] = [{
        "character": "Fuzzby", "belongs": ["wrong"], "banned": []
    }]
    validated = D.AnimationDirection.model_validate(direction)
    assert [item.model_dump() for item in validated.motionVocabulary] == [
        item.model_dump() for item in D.canonical_motion_vocabulary()
    ]


def test_animation_prompt_is_compiled_from_typed_beat_truth_not_free_prose():
    primary = (
        "Fuzzby enters too fast, visibly loads the springy leaf with his weight, then "
        "the leaf recoil launches him into one tucked rotation and an upright hover.")
    provider_action = (
        "Fuzzby holds the chest-forward recovery while his body still wobbles and "
        "Zenny remains level on the safe parallel route.")
    handoff = "Fuzzby hovers upright in drifting pollen while Zenny watches nearby."
    shot = {
        "charactersInFrame": ["Fuzzby", "Zenny"],
        "comedyContractsApproved": [{
            "beatCode": "1.B1", "mode": "BIG",
            "physicalStaging": {"contactAndWeight": (
                "Fuzzby's sideways momentum depresses the leaf; the leaf bends, stores "
                "force, then snaps him upright.")},
        }],
        "dialogueLines": [
            {"speaker": "Fuzzby", "exactText": "Nailed it.",
             "startSec": 7.2, "endSec": 8.0},
        ],
        "durationSec": 9,
        "shotId": "S1.SH1A",
        "sourceShotId": "S1.SH1",
        "purpose": "Protect two near-misses before the flower contact and leaf recoil.",
    }
    direction = {
        "providerPrompt": "Make a nice cinematic bee video.",
        "generationGoal": "Fuzzby's apparent expertise collapses into a false triumph.",
        "dramaticBeat": "Visible failure becomes performed success.",
        "performanceArc": "Overcommitted speed resolves into an over-proud recovery.",
        "physicalCauseAndEffect": "His weight bends the leaf; stored force returns him upright.",
        "cameraBehaviour": "A bee-height chase settles to a medium hold for the button.",
        "creativeTranslation": {
            "interpretation": {
                "mechanism": "His body disproves the authority he performs.",
                "emotionalHeart": "Zenny sees the failure and stays affectionately present.",
            },
            "gagClocks": [{
                "beatCode": "1.B1", "providerAction": provider_action,
                "recoveryHold": "Hold the proud wobbling recovery.",
                "recoveryHoldSec": 2.2,
            }],
        },
        "referenceContract": [
            {"assetTag": "@Image1", "role": "opening_frame",
             "controls": "the exact approved opening composition"},
            {"assetTag": "@Image2", "role": "character_identity",
             "controls": "Fuzzby's exact turnaround identity and proportions"},
            {"assetTag": "@Audio1", "role": "audio",
             "controls": "the approved voice performance"},
        ],
        "stagePlan": [{
            "stageNumber": 1,
            "startSec": 0.0,
            "endSec": 9.0,
            "beatIds": ["1.B1"],
            "purpose": "Chase, recoil and false triumph",
            "initialOrCarriedState": "The approved chase is already moving through frame.",
            "cause": "Fuzzby's overcommitted speed loads the springy leaf.",
            "primaryEvent": primary,
            "emotionOrCameraAnalysis": "Keep the contact readable, then settle for the lie.",
            "observableEndState": handoff,
        }],
        "consistencyContract": [
            "Supplied Fuzzby and Zenny references as identity and scale locks; do not "
            "redesign, substitute species or add extra cast.",
        ],
        "geography": [
            "The corridor runs frame-left to frame-right; the camera stays south at bee height."
        ],
        "surgicalSafeguards": ["the leaf bend, recoil and landing remain one causal chain"],
        "continuityFinish": handoff,
        "audioContract": "Use @Audio1 unchanged; retain wing, leaf and pollen foley; no music.",
    }

    prompt = D.compile_animation_provider_prompt(shot, direction)

    assert "Make a nice cinematic bee video" not in prompt
    assert primary in prompt
    assert provider_action in prompt
    assert handoff in prompt
    assert "@图1 is the first frame" in prompt
    assert "@图1 is the first frame and the previous shot's approved final frame" in prompt
    assert "Slots: @图1=opening_frame; @图2=Fuzzby; @Audio1=audio; never swap." in prompt
    assert "Angles: @图2=one Fuzzby; views are not extra characters." in prompt
    assert "AUDIO-AUTHORITY: @Audio1 is the sole authority" in prompt
    assert "[Timestamp Script Storyboard]" not in prompt
    assert "Stage 1: 0-9s" not in prompt
    assert "Hold: 2.2s" in prompt
    assert "Spoken action: Fuzzby: {Nailed it.}" in prompt
    assert "Audio cues:" not in prompt
    assert "Physics: Fuzzby's sideways momentum depresses the leaf" in prompt
    assert "Include two readable near-misses before the first impact." in prompt
    assert ("Exactly one Fuzzby and one Zenny throughout; no duplicates of either "
            "character.") in prompt
    assert "@图2 defines exactly one Fuzzby identity/scale only" in prompt
    assert "[AUDIO AND EXCLUSIONS]" in prompt
    assert "No narration. No improvised or extra words." in prompt
    assert "no duplicated cast members" in prompt
    assert "Seedance may generate non-verbal music, ambience and SFX" in prompt
    assert "Hold: 2.2s" in prompt and "approximately 2.2s" not in prompt
    # Length is advisory. The production gate measures whether the compiled prompt
    # delivers the beat and satisfies the Seedance/craft contracts.
    assert len(prompt.split()) > 0


def test_animation_provider_prompt_emits_deterministic_dialogue_placements():
    shot = {
        "shotId": "7.B3.S1",
        "durationSec": 20,
        "charactersInFrame": ["Howey", "Aida", "Keen", "Squeaky"],
        "dialogueLines": [
            {"speaker": "Howey", "exactText": "He jumped in?!",
             "delivery": "startled and immediate", "startSec": 0.3, "endSec": 1.4},
            {"speaker": "Aida", "exactText": "He didn’t think twice.",
             "delivery": "quiet and immediate", "startSec": 1.35, "endSec": 3.8},
            {"speaker": "Keen", "exactText": "I’ve got you!",
             "delivery": "breathy surface gasp", "startSec": 10.6, "endSec": 12.7},
            {"speaker": "Keen", "exactText": "I’ve got this… I’ve got this…",
             "delivery": "breathless surface self-command", "startSec": 13.2,
             "endSec": 16.0},
        ],
    }
    direction = {
        "providerPrompt": "Make a loose rescue scene.",
        "generationGoal": "Keep rescue physics and speech timing causal.",
        "dramaticBeat": "Keen chooses courage while still failing to free Squeaky.",
        "performanceArc": "Witness fear becomes Keen surface-breath determination.",
        "physicalCauseAndEffect": "Keen surfaces to speak, then dives back under silently.",
        "cameraBehaviour": "Tight witness opening, no cuts, no handheld, then storm-water struggle.",
        "creativeTranslation": {"interpretation": {
            "mechanism": "Surface breaks own all clean speech.",
            "emotionalHeart": "Keen reassures Squeaky before the rescue is solved.",
        }},
        "referenceContract": [{"assetTag": "@Audio1", "role": "audio",
                               "controls": "the approved voice performance"}],
        "stagePlan": [{
            "stageNumber": 1,
            "startSec": 0.0,
            "endSec": 20.0,
            "beatIds": ["7.B3"],
            "purpose": "Witness, dive and unresolved first rescue contact",
            "initialOrCarriedState": "Howey and Aida look out to the distant boat.",
            "cause": "Keen has jumped into the storm water.",
            "primaryEvent": "Keen surfaces to speak and dives back under silently.",
            "emotionOrCameraAnalysis": "Keep surface breath and underwater silence readable.",
            "observableEndState": "Squeaky remains trapped and the rescue is unresolved.",
        }],
        "consistencyContract": ["No clean underwater speech."],
        "geography": ["Storm-cove shore and storm water."],
        "surgicalSafeguards": ["Squeaky is not freed in this shot."],
        "continuityFinish": "Squeaky remains trapped and the rescue is unresolved.",
        "audioContract": "Use @Audio1 unchanged; no music.",
    }

    prompt = D.compile_animation_provider_prompt(shot, direction)

    assert "16:9" not in prompt
    assert "480p" not in prompt
    assert "model" not in prompt.lower()
    assert "no cuts" not in prompt.lower()
    assert "no handheld" not in prompt.lower()
    assert "Spoken action: Howey, startled and immediate: {He jumped in?!}" in prompt
    assert "Spoken action: Aida, quiet and immediate: {He didn’t think twice.}" in prompt
    assert "Spoken action: Keen, breathy surface gasp: {I’ve got you!}" in prompt
    assert ("Spoken action: Keen, breathless surface self-command: "
            "{I’ve got this… I’ve got this…}") in prompt


def test_character_reference_label_accepts_authority_first_contracts():
    assert D._character_reference_label("Controls Hero's identity and scale.") == "Hero"
    assert D._character_reference_label("Controls Hero’s Mum’s identity and scale.") == "Hero’s Mum"
    assert D._character_reference_label("Guide's exact identity and turnaround.") == "Guide"


def test_creative_translation_derives_redundant_gag_count():
    payload = {
        "interpretation": {
            "jokeOrAche": "A visible action unfolds.",
            "mechanism": "Cause produces effect.",
            "statusBefore": "The relationship is unresolved.",
            "statusAfter": "The relationship advances.",
            "audienceProgression": ["anticipation", "change", "recognition"],
            "emotionalHeart": "The relationship remains readable.",
        },
        "gagClocks": [],
        "generationDesign": {
            "packagingDecision": "single-unit",
            "completeGagArcCount": 7,
            "densityJudgement": "Playable.",
            "splitOrNonSplitRationale": "The unit remains coherent.",
            "handoffState": "The final state is held.",
        },
    }

    result = D.CreativeTranslationDirection.model_validate(payload)

    assert result.generationDesign.completeGagArcCount == 0


def test_physics_comes_from_general_approved_staging_registry():
    shot = {
        "shotId": "S9.SH2B", "durationSec": 6,
        "dialogueLines": [],
        "physicalStagings": [{
            "beatCode": "9.B4",
            "contactAndWeight": "The lantern pulls the rope taut; the post bends, stores force, then returns upright.",
        }],
    }
    direction = {
        "generationGoal": "A rope-load gag resolves into a held recovery.",
        "creativeTranslation": {"interpretation": {}, "gagClocks": []},
        "referenceContract": [], "geography": ["The deck runs left to right."],
        "stagePlan": [{
            "stageNumber": 1, "beatIds": ["9.B4"], "startSec": 0, "endSec": 6,
            "purpose": "Rope load", "initialOrCarriedState": "The lantern hangs under tension.",
            "cause": "The character transfers weight into the rope.",
            "primaryEvent": "The rope tightens and the post returns upright.",
            "emotionOrCameraAnalysis": "Hold the camera until the force transfer reads.",
            "observableEndState": "The post stands upright while the rope remains taut.",
        }],
        "consistencyContract": ["Keep the deck axis stable."],
        "surgicalSafeguards": [], "continuityFinish": "The rope remains taut.",
        "audioContract": "Natural deck and rope foley only.",
    }
    prompt = D.compile_animation_provider_prompt(shot, direction)
    assert "Physics: The lantern pulls the rope taut" in prompt
    assert "Seedance may generate non-verbal music, ambience and SFX" in prompt


def test_animation_compiler_emits_continuous_internal_units_as_timed_phases():
    shot = {
        "shotId": "S1.SH9A", "durationSec": 12, "charactersInFrame": ["A", "B"],
        "dialogueLines": [],
    }
    direction = {
        "durationSec": 12,
        "generationGoal": "A fast pursuit becomes a visible impact and proud recovery.",
        "creativeTranslation": {"interpretation": {}, "gagClocks": []},
        "referenceContract": [],
        "geography": ["The route runs left to right with visible depth ahead."],
        "shotPlan": [
            {"shotNumber": 1, "framingLensAndCamera": "A low pursuit camera follows slightly late.",
             "causalAction": "A zig-zags while B holds a clean parallel line."},
            {"shotNumber": 2, "framingLensAndCamera": "The camera holds the impact in profile.",
             "causalAction": "A compresses the flower and loads the springy leaf."},
            {"shotNumber": 3, "framingLensAndCamera": "The camera rises and settles for the finish.",
             "causalAction": "The leaf recoils A into one flip and a proud wobbling hover."},
        ],
        "stagePlan": [{
            "stageNumber": 1, "beatIds": ["9.B1"],
            "initialOrCarriedState": "The pursuit is already moving through frame.",
            "cause": "A overcommits to the route.",
            "primaryEvent": "A crosses the route, loads the leaf and rebounds upright.",
            "emotionOrCameraAnalysis": "The pursuit turns speed into readable physical comedy.",
            "observableEndState": "A hovers upright while B watches.",
        }],
        "consistencyContract": ["Keep identity and route direction stable."],
        "surgicalSafeguards": [], "continuityFinish": "A hovers upright.",
        "audioContract": "Natural movement and plant foley only.",
    }
    prompt = D.compile_animation_provider_prompt(shot, direction)
    assert "[Timed Action Phases" in prompt
    assert "One continuous Seedance render" in prompt
    assert "Shot 1:" not in prompt
    assert prompt.index("Phase 1:") < prompt.index("Phase 2:") < prompt.index("Phase 3:")
    assert "follows slightly late" in prompt
    assert "compresses the flower and loads the springy leaf" in prompt
    assert "one flip and a proud wobbling hover" in prompt


def test_animation_compiler_normalizes_seedance_ready_watch_prompt():
    shot = {
        "shotId": "3.B1.S1",
        "durationSec": 16,
        "charactersInFrame": ["Keen", "Keen's Mum"],
        "dialogueLines": [
            {"speaker": "Keen's Mum", "exactText": "Are you sure?", "startSec": 4, "endSec": 6},
            {"speaker": "Keen", "exactText": "I've got this.", "startSec": 7, "endSec": 9},
        ],
    }
    direction = {
        "durationSec": 16,
        "generationGoal": "Create a 16-second reference-to-video unit where Keen packs the boat.",
        "creativeTranslation": {"interpretation": {}, "gagClocks": []},
        "referenceContract": [
            {"assetTag": "@图1", "role": "location", "controls": "the approved pier and boat"},
            {"assetTag": "@图2", "role": "character_identity", "controls": "Keen identity and scale"},
            {"assetTag": "@图3", "role": "character_identity", "controls": "Mum identity and scale"},
            {"assetTag": "@图4", "role": "opening_frame", "controls": "the exact first frame"},
            {"assetTag": "@Audio1", "role": "audio", "controls": "the approved voice performance"},
        ],
        "geography": ["The pier runs toward open water with the boat screen-right."],
        "shotPlan": [
            {
                "shotNumber": 1,
                "framingLensAndCamera": "Shot 1: medium-wide from the island end.",
                "causalAction": "Keen places the rolled map and satchel into the boat.",
                "landingImage": "Keen's hand hovers near the packed satchel.",
                "dialogueLineIndexes": [1],
                "dialogueDirections": ["speaks gently"],
            },
            {
                "shotNumber": 2,
                "framingLensAndCamera": "Cut to. Shot 2: closer two-shot beside the boat.",
                "causalAction": "Keen catches himself before checking the satchel again.",
                "landingImage": "Keen and Mum hold beside the packed boat.",
                "dialogueLineIndexes": [2],
                "dialogueDirections": ["answers brightly"],
            },
        ],
        "stagePlan": [{
            "stageNumber": 1, "beatIds": ["3.B1"],
            "initialOrCarriedState": "Keen starts beside the boat.",
            "primaryEvent": "Keen packs and overchecks his supplies.",
            "emotionOrCameraAnalysis": "The low camera keeps the boat and Mum readable.",
            "observableEndState": "Keen and Mum hold beside the packed boat.",
        }],
        "consistencyContract": ["Keep identity, boat position, and prop ownership stable."],
        "surgicalSafeguards": ["Keen has bare wrists"],
        "continuityFinish": "Keen and Mum hold beside the packed boat.",
        "audioContract": "Use @Audio1 unchanged; no music.",
    }
    prompt = D.compile_animation_provider_prompt(shot, direction)

    assert "16-second" not in prompt
    assert "16:9" not in prompt
    assert "Camera: Shot 1:" not in prompt
    assert "Camera: Cut to" not in prompt
    assert "[Performance Sequence]" not in prompt
    assert "@Audio1 guides dialogue timing and mouth shapes" in prompt
    assert "No extra voices." in prompt
    assert prompt.count("{Are you sure?}") == 1
    assert prompt.count("{I've got this.}") == 1


def test_animation_context_merges_voice_director_timing_before_compile():
    shot = {
        "shotId": "3.B2.S1",
        "durationSec": 9,
        "dialogueLines": [{
            "speaker": "Keen",
            "text": "Like you said... it is part of growing up.",
            "dialogueOccurrenceId": "dialogue-1",
        }],
    }
    ledger = {
        "departmentWork": {
            "voice": {
                "candidate": {
                    "output": {
                        "lines": [{
                            "dialogueOccurrenceId": "dialogue-1",
                            "startsAtSec": 2.1,
                            "estimatedDurationSec": 3.2,
                        }]
                    }
                }
            }
        }
    }

    effective = R._with_effective_dialogue_timing(shot, ledger)
    cue = D.emission.dialogue_cues(
        effective["dialogueLines"], duration_sec=shot["durationSec"])[0]

    assert cue["startSec"] == 2.1
    assert cue["endSec"] == pytest.approx(5.3)
    assert cue["exactText"] == "Like you said... it is part of growing up."


def test_relay_animation_gets_previous_final_frame_reference_by_default():
    shot = {
        "shotId": "3.B2.S1",
        "sourceType": "relay",
        "sourceShotId": "3.B1.S1",
        "charactersInFrame": ["Keen", "Keen's Mum"],
    }
    slots = R._effective_reference_slots({}, shot, "referenceSlots", "3", "Ep1")
    assert slots == {
        "@图1": "previous shot final frame",
        "@图2": "scene plate",
        "@图3": "Keen",
        "@图4": "Keen's Mum",
    }


def test_animation_slots_append_all_required_continuity_props(monkeypatch):
    shot = {
        "shotId": "6.B3.S1",
        "sourceType": "relay",
        "sourceShotId": "6.B1.S1",
        "charactersInFrame": ["Aida"],
        "referenceSlots": {
            "@图1": "previous shot final frame",
            "@图2": "scene plate",
            "@图3": "Aida",
            "@Audio1": "voice track",
        },
    }
    monkeypatch.setattr(
        R, "_required_prop_reference_roles",
        lambda *args: ["prop:story_vehicle", "prop:story_vehicle_loaded_state"],
    )

    slots = R._effective_reference_slots({}, shot, "referenceSlots", "6", "Ep1")

    assert slots["@图4"] == "prop:story_vehicle"
    assert slots["@图5"] == "prop:story_vehicle_loaded_state"
    assert slots["@Audio1"] == "voice track"


def test_relay_reference_bundle_blocks_missing_scene_and_character_refs():
    shot = {
        "shotId": "3.B2.S1",
        "sourceType": "relay",
        "sourceShotId": "3.B1.S1",
        "charactersInFrame": ["Keen", "Keen's Mum"],
    }
    report = R._relay_reference_bundle_report(
        shot, [{"role": "previous shot final frame"}])
    assert report["ok"] is False
    assert report["missing"] == ["scene plate", "Keen", "Keen's Mum"]


def test_relay_reference_bundle_accepts_complete_bundle():
    shot = {
        "shotId": "3.B2.S1",
        "sourceType": "relay",
        "sourceShotId": "3.B1.S1",
        "charactersInFrame": ["Keen", "Keen's Mum"],
    }
    report = R._relay_reference_bundle_report(shot, [
        {"role": "previous shot final frame"},
        {"role": "scene plate"},
        {"role": "Keen"},
        {"role": "Keen's Mum"},
    ])
    assert report["ok"] is True


def test_relay_reference_bundle_requires_explicit_story_prop_authority():
    shot = {
        "shotId": "3.B3.S1",
        "sourceType": "relay",
        "sourceShotId": "3.B1.S1",
        "charactersInFrame": ["Keen", "Keen's Mum"],
        "referenceSlots": {
            "@图1": "previous shot final frame",
            "@图2": "Keen",
            "@图3": "Keen's Mum",
            "@图4": "scene plate",
            "@图5": "prop:keen_fathers_wristbands",
        },
    }
    report = R._relay_reference_bundle_report(shot, [
        {"role": "previous shot final frame"},
        {"role": "scene plate"},
        {"role": "Keen"},
        {"role": "Keen's Mum"},
    ])
    assert report["ok"] is False
    assert report["missing"] == ["prop:keen_fathers_wristbands"]


def test_scene_continuity_locks_are_emitted_into_animation_prompt():
    shot = {
        "shotId": "3.B2.S1",
        "sourceType": "relay",
        "sourceShotId": "3.B1.S1",
        "charactersInFrame": ["Keen", "Keen's Mum"],
        "durationSec": 9,
        "dialogueLines": [],
        "sceneContinuityLocks": [{
            "id": "scene3-boat-contents-v1",
            "label": "Keen boat contents and departure props",
            "value": (
                "The small sailboat contains Keen's practical departure items: open "
                "satchel, rolled blanket, folded map, and small food pouch. Keep them "
                "continuous across Scene 3 unless a later approved shot visibly moves them."
            ),
            "forbidden": (
                "No crystal baskets, ceremonial loads, aquamarine stones, glowing crystals, "
                "or random cargo in the boat."
            ),
        }],
    }
    direction = {
        "shotId": "3.B2.S1",
        "durationSec": 9,
        "taskMode": "reference-to-video",
        "pacingMode": "storyline",
        "generationGoal": "Keen looks out at the water and tries to sound brave.",
        "deliveryPlan": "Let courage show through a visible swallow.",
        "creativeTranslation": {
            "interpretation": {
                "mechanism": "The water makes the step visible.",
                "emotionalHeart": "Keen is loved while he is scared.",
            },
            "gagClocks": [],
        },
        "dramaticBeat": "Keen faces the water and borrows grown-up courage.",
        "audienceBefore": "Keen is supported.",
        "audienceAfter": "Keen is still scared but trying.",
        "beatOwner": "Keen",
        "performanceFreedom": "Allow small eye and breath movement.",
        "performanceArc": "Supported to frightened to trying.",
        "physicalCauseAndEffect": "The open water draws his gaze and tightens his body.",
        "cameraBehaviour": "A close two-shot favours Keen without losing Mum.",
        "timingAndRhythm": "Swallow, line, hold.",
        "landingBreath": "Hold the quiet aftermath.",
        "directionDensity": "guided",
        "shotPlan": [{
            "shotNumber": 1,
            "purpose": "Make the water feel large.",
            "framingLensAndCamera": "Medium two-shot at child eye height.",
            "causalAction": "Keen looks from Mum to the water and swallows.",
            "observablePerformance": "Mum stays quiet and loving while Keen tries to stay steady.",
            "compositionLightAndMaterials": "Warm pier light, water behind Keen.",
            "landingImage": "Keen and Mum remain beside the boat with the water ahead.",
            "dialogueLineIndexes": [],
            "dialogueDirections": [],
        }],
        "timingBeats": [],
        "witnessStagingSides": [
            "Keen's Mum remains screen-left while Keen holds screen-right."
        ],
        "stagePlan": [{
            "stageNumber": 1,
            "beatIds": ["3.B2"],
            "purpose": "Borrowed courage",
            "initialOrCarriedState": "Keen and Mum are beside the boat.",
            "cause": "The water looks large.",
            "primaryEvent": "Keen looks out and swallows.",
            "emotionOrCameraAnalysis": "Stay close enough to read his face.",
            "observableEndState": "Keen holds beside Mum, still looking at the water.",
        }],
        "geography": ["Keen and Mum stand on the pier beside the small sailboat."],
        "attributeOwnership": [],
        "environmentContract": [],
        "referenceContract": [],
        "openingCarriedState": "Keen and Mum remain beside the boat.",
        "openingMotionBridge": (
            "Keen completes the inherited movement, withdraws both empty paws and steps "
            "clear before Mum approaches the prop."),
        "actionOwnership": [
            "Mum alone opens the container and removes the object.",
            "Keen never reaches into the container or touches the object until handoff.",
        ],
        "consistencyContract": ["Keen and Mum stay in the same pier geography."],
        "audioContract": "No dialogue.",
        "continuityFinish": "Keen stays beside Mum at the boat.",
        "surgicalSafeguards": [],
    }

    prompt = D.compile_animation_provider_prompt(shot, direction)

    assert "[Scene Continuity State]" in prompt
    assert "open satchel, rolled blanket, folded map, and small food pouch" in prompt
    assert "No crystal baskets" in prompt
    assert "their stillness and the hold length carry the emotional truth" in prompt
    assert "carry the joke" not in prompt
    assert "[Opening Motion Bridge]" in prompt
    assert "[ACTION OWNERSHIP]" in prompt
    assert prompt.index("[Opening Motion Bridge]") < prompt.index("[Camera and Shot Plan]")
    assert prompt.index("[ACTION OWNERSHIP]") < prompt.index("[Camera and Shot Plan]")
    assert R._scene_state_prompt_report(shot, prompt)["ok"] is True


def test_scene_continuity_locks_block_when_missing_from_prompt():
    shot = {
        "shotId": "3.B2.S1",
        "sceneContinuityLocks": [{
            "label": "Keen boat contents and departure props",
            "value": "The small sailboat contains open satchel and folded map.",
        }],
    }
    report = R._scene_state_prompt_report(shot, "Keen looks at the water.")
    assert report["ok"] is False
    assert report["missing"] == ["Keen boat contents and departure props"]


def test_relay_final_frame_is_state_handoff_not_geography_master():
    shot = {
        "shotId": "3.B2.S1",
        "sourceType": "relay",
        "sourceShotId": "3.B1.S1",
        "charactersInFrame": ["Keen", "Keen's Mum"],
        "durationSec": 9,
        "dialogueLines": [],
        "sceneContinuityLocks": [{
            "id": "scene3-boat-contents-v1",
            "label": "Keen boat contents and departure props",
            "value": "The small sailboat contains open satchel, rolled blanket, folded map, and small food pouch.",
            "forbidden": "No random cargo in the boat.",
        }],
    }
    direction = {
        "shotId": "3.B2.S1",
        "durationSec": 9,
        "taskMode": "reference-to-video",
        "pacingMode": "storyline",
        "generationGoal": "Keen looks toward the water while Mum supports him.",
        "deliveryPlan": "Preserve scene geography from the plate.",
        "creativeTranslation": {
            "interpretation": {
                "mechanism": "The wider pier and boat geography carry the emotional stakes.",
                "emotionalHeart": "Keen is loved while he is scared.",
            },
            "gagClocks": [],
        },
        "dramaticBeat": "Keen faces the water.",
        "audienceBefore": "Keen is supported.",
        "audienceAfter": "Keen tries to be brave.",
        "beatOwner": "Keen",
        "performanceFreedom": "Allow small eye and breath movement.",
        "performanceArc": "Supported to frightened to trying.",
        "physicalCauseAndEffect": "The water draws his gaze.",
        "cameraBehaviour": "A close shot favours Keen without losing the boat.",
        "timingAndRhythm": "Look, swallow, hold.",
        "landingBreath": "Hold the quiet aftermath.",
        "directionDensity": "guided",
        "shotPlan": [{
            "shotNumber": 1,
            "purpose": "Make the water feel large without losing the pier.",
            "framingLensAndCamera": "Medium two-shot beside the boat.",
            "causalAction": "Keen looks to the water.",
            "observablePerformance": "Keen tries to stay steady.",
            "compositionLightAndMaterials": "Warm pier light and visible boat wood.",
            "landingImage": "Keen and Mum remain beside the boat with the pier readable.",
            "dialogueLineIndexes": [],
            "dialogueDirections": [],
        }],
        "timingBeats": [],
        "witnessStagingSides": [],
        "stagePlan": [{
            "stageNumber": 1,
            "beatIds": ["3.B2"],
            "purpose": "Borrowed courage",
            "initialOrCarriedState": "Keen and Mum remain emotionally close after the previous shot.",
            "cause": "The water looks large.",
            "primaryEvent": "Keen looks out.",
            "emotionOrCameraAnalysis": "Stay close but keep the boat and pier readable.",
            "observableEndState": "Keen holds beside the water.",
        }],
        "geography": ["Keen and Mum stand on the pier beside the small sailboat."],
        "attributeOwnership": [],
        "environmentContract": [],
        "referenceContract": [{
            "assetTag": "@图1",
            "role": "opening_frame",
            "controls": "the previous shot final frame",
            "scope": "continuity",
        }, {
            "assetTag": "@图4",
            "role": "location",
            "controls": "the pier, boat, shoreline, water and daylight",
            "scope": "scene",
        }],
        "openingCarriedState": "Keen and Mum remain emotionally close after the previous shot.",
        "consistencyContract": ["The boat stays beside the pier."],
        "audioContract": "No dialogue.",
        "continuityFinish": "Keen remains beside the same packed boat.",
        "surgicalSafeguards": [],
    }

    prompt = D.compile_animation_provider_prompt(shot, direction)

    assert ("@图1 is the first frame and the previous shot's approved final frame."
            in prompt)
    assert "Use it only for carried character state" in prompt
    assert "Do not use it as the scene geography" in prompt
    assert "Match its staging and positions exactly" not in prompt
    assert "@图2 defines scene/layout/light only" in prompt
    assert "open satchel, rolled blanket, folded map, and small food pouch" in prompt


def test_scene_continuity_persists_even_when_cast_changes():
    shot = {
        "shotId": "3.B4.S1",
        "charactersInFrame": ["Keen"],
        "durationSec": 8,
        "dialogueLines": [],
        "sceneContinuityLocks": [{
            "id": "scene3-boat-contents-v1",
            "label": "Keen boat contents and departure props",
            "value": (
                "The small sailboat contains Keen's practical departure items: open "
                "satchel, rolled blanket, folded map, and small food pouch. Keep them "
                "continuous across Scene 3 unless a later approved shot visibly moves them."
            ),
            "forbidden": "No random cargo in the boat.",
            "sourceShotId": "3.B1.S1",
        }],
    }
    direction = {
        "shotId": "3.B4.S1",
        "durationSec": 8,
        "taskMode": "reference-to-video",
        "pacingMode": "storyline",
        "generationGoal": "Keen sits alone beside the boat and gathers himself.",
        "deliveryPlan": "Keep the scene quiet and continuous.",
        "creativeTranslation": {
            "interpretation": {
                "mechanism": "The unchanged boat contents show the same lived-in scene.",
                "emotionalHeart": "Keen is alone now, but the scene remembers the goodbye.",
            },
            "gagClocks": [],
        },
        "dramaticBeat": "Keen is alone with the weight of leaving.",
        "audienceBefore": "Mum has been present.",
        "audienceAfter": "The scene continues after Mum leaves.",
        "beatOwner": "Keen",
        "performanceFreedom": "Allow small breath and eye movement.",
        "performanceArc": "Held together to privately uncertain.",
        "physicalCauseAndEffect": "Mum's absence makes the packed boat feel more real.",
        "cameraBehaviour": "A quiet held shot keeps the boat readable.",
        "timingAndRhythm": "Slow breath, look to boat, hold.",
        "landingBreath": "Hold the stillness.",
        "directionDensity": "guided",
        "shotPlan": [{
            "shotNumber": 1,
            "purpose": "Show the scene continuing without Mum.",
            "framingLensAndCamera": "Medium shot beside the boat.",
            "causalAction": "Keen looks at the packed boat.",
            "observablePerformance": "Keen tries to stay composed.",
            "compositionLightAndMaterials": "Warm dock light and boat wood remain consistent.",
            "landingImage": "Keen remains beside the same packed boat.",
            "dialogueLineIndexes": [],
            "dialogueDirections": [],
        }],
        "timingBeats": [],
        "witnessStagingSides": [],
        "stagePlan": [{
            "stageNumber": 1,
            "beatIds": ["3.B4"],
            "purpose": "Private courage",
            "initialOrCarriedState": "Keen is beside the packed boat.",
            "cause": "Mum has left the frame.",
            "primaryEvent": "Keen looks at the packed boat and breathes.",
            "emotionOrCameraAnalysis": "Let the unchanged boat carry continuity.",
            "observableEndState": "Keen remains beside the same packed boat.",
        }],
        "geography": ["The boat stays beside the pier."],
        "attributeOwnership": [],
        "environmentContract": [],
        "referenceContract": [],
        "openingCarriedState": "Keen is beside the packed boat.",
        "consistencyContract": ["Keen stays beside the boat."],
        "audioContract": "No dialogue.",
        "continuityFinish": "Keen remains beside the same packed boat.",
        "surgicalSafeguards": [],
    }

    prompt = D.compile_animation_provider_prompt(shot, direction)

    assert "Keen's Mum" not in prompt
    assert "open satchel, rolled blanket, folded map, and small food pouch" in prompt
    assert R._scene_state_prompt_report(shot, prompt)["ok"] is True


def test_animation_reference_controls_lines_are_normalized_to_defines():
    shot = {
        "shotId": "3.B2.S1",
        "charactersInFrame": ["Keen"],
        "durationSec": 9,
        "dialogueLines": [],
    }
    direction = {
        "shotId": "3.B2.S1",
        "durationSec": 9,
        "taskMode": "reference-to-video",
        "pacingMode": "storyline",
        "generationGoal": "Keen looks out at the water.",
        "deliveryPlan": "Keep the beat simple.",
        "creativeTranslation": {
            "interpretation": {
                "mechanism": "The water makes the step visible.",
                "emotionalHeart": "Keen is loved while he is scared.",
            },
            "gagClocks": [],
        },
        "dramaticBeat": "Keen faces the water.",
        "audienceBefore": "Keen is supported.",
        "audienceAfter": "Keen tries to be brave.",
        "beatOwner": "Keen",
        "performanceFreedom": "Allow small eye and breath movement.",
        "performanceArc": "Supported to frightened to trying.",
        "physicalCauseAndEffect": "The water draws his gaze.",
        "cameraBehaviour": "A close shot favours Keen.",
        "timingAndRhythm": "Look, swallow, hold.",
        "landingBreath": "Hold the quiet aftermath.",
        "directionDensity": "guided",
        "shotPlan": [{
            "shotNumber": 1,
            "purpose": "Make the water feel large.",
            "framingLensAndCamera": "Medium shot at child eye height.",
            "causalAction": "Keen looks to the water.",
            "observablePerformance": "Keen tries to stay steady.",
            "compositionLightAndMaterials": "Warm pier light.",
            "landingImage": "Keen remains beside the water.",
            "dialogueLineIndexes": [],
            "dialogueDirections": [],
        }],
        "timingBeats": [],
        "witnessStagingSides": [],
        "stagePlan": [{
            "stageNumber": 1,
            "beatIds": ["3.B2"],
            "purpose": "Borrowed courage",
            "initialOrCarriedState": "Keen is beside the boat.",
            "cause": "The water looks large.",
            "primaryEvent": "Keen looks out.",
            "emotionOrCameraAnalysis": "Stay close.",
            "observableEndState": "Keen holds beside the water.",
        }],
        "geography": ["Keen stands on the pier."],
        "attributeOwnership": [],
        "environmentContract": [],
        "referenceContract": [{
            "assetTag": "@图2",
            "role": "character_identity",
            "controls": (
                "Keen’s character identity, proportions and scale only; do not add "
                "wristbands"
            ),
            "scope": "canon",
        }],
        "openingCarriedState": "Keen is beside the boat.",
        "consistencyContract": ["Keen stays on the pier."],
        "audioContract": "No dialogue.",
        "continuityFinish": "Keen stays beside the water.",
        "surgicalSafeguards": [],
    }
    prompt = D.compile_animation_provider_prompt(shot, direction)

    assert "@图2 controls" not in prompt
    assert "@图1 defines exactly one Keen identity, proportions, scale and approved wearable state:" in prompt
    assert "do not add wristbands" in prompt
    assert "exclude background, pose, unrelated props and scene" in prompt


def test_animation_character_reference_preserves_approved_wearable_ownership():
    line = D._character_reference_authority_line(
        "@图2",
        "Keen",
        "Keen identity and scale",
        [
            "Keen owns exactly two aged-gold open cuffs with blank settings, one on each wrist",
            "The boat owns the rolled blanket",
        ],
    )

    assert "approved wearable state" in line
    assert "exactly two aged-gold open cuffs with blank settings" in line
    assert "unrelated props" in line


def test_animation_compiler_injects_identity_record_state_lock_when_director_omits_it():
    shot = {
        "shotId": "X.B1.S1",
        "charactersInFrame": ["Hero"],
        "characterStateLocks": {
            "Hero": (
                "Hero approved wearable state: matching blank open cuffs worn on both "
                "wrists; no crystals and no glow"
            )
        },
    }
    direction = {
        "durationSec": 8,
        "generationGoal": "Hero gathers focus while preserving the approved visible state.",
        "dramaticBeat": "Hero becomes ready.",
        "audienceBefore": "Hero is waiting.",
        "audienceAfter": "Hero is ready.",
        "beatOwner": "Hero",
        "performanceFreedom": "Allow natural breathing and eye movement.",
        "performanceArc": "Waiting to focused.",
        "physicalCauseAndEffect": "The scene begins and Hero looks ahead.",
        "cameraBehaviour": "Hold a steady medium view.",
        "timingAndRhythm": "Look, breathe, settle.",
        "landingBreath": "Hold the focused expression.",
        "directionDensity": "guided",
        "creativeTranslation": {"interpretation": {}, "gagClocks": []},
        "stagePlan": [{
            "stageNumber": 1,
            "beatIds": ["X.B1"],
            "purpose": "Hold the character state.",
            "initialOrCarriedState": "Hero waits.",
            "cause": "The scene begins.",
            "primaryEvent": "Hero looks ahead.",
            "emotionOrCameraAnalysis": "Keep the thought readable.",
            "observableEndState": "Hero remains ready.",
        }],
        "shotPlan": [{
            "shotNumber": 1,
            "purpose": "Show Hero ready.",
            "framingLensAndCamera": "Medium eye-level shot.",
            "causalAction": "Hero looks ahead.",
            "observablePerformance": "Hero breathes and focuses.",
            "compositionLightAndMaterials": "Soft daylight.",
            "landingImage": "Hero remains ready.",
            "dialogueLineIndexes": [],
            "dialogueDirections": [],
        }],
        "geography": [],
        "actionOwnership": [],
        "attributeOwnership": [],
        "environmentContract": [],
        "referenceContract": [{
            "assetTag": "@图1",
            "role": "character_identity",
            "controls": "Hero identity and scale only",
            "scope": "canon",
        }],
        "openingCarriedState": "Hero waits.",
        "consistencyContract": [],
        "audioContract": "No dialogue.",
        "continuityFinish": "Hero waits.",
        "surgicalSafeguards": [],
    }

    prompt = D.compile_animation_provider_prompt(shot, direction)

    assert "approved wearable state" in prompt
    assert "matching blank open cuffs worn on both wrists" in prompt
    assert "no crystals and no glow" in prompt
    assert "[ATTRIBUTE OWNERSHIP]" in prompt


def test_animation_first_frame_owns_line_is_normalized_to_excluded_first_frame():
    shot = {
        "shotId": "3.B2.S1",
        "charactersInFrame": ["Keen"],
        "durationSec": 9,
        "dialogueLines": [],
    }
    direction = {
        "shotId": "3.B2.S1",
        "durationSec": 9,
        "taskMode": "reference-to-video",
        "pacingMode": "storyline",
        "generationGoal": "Keen looks out at the water.",
        "deliveryPlan": "Keep the beat simple.",
        "creativeTranslation": {
            "interpretation": {
                "mechanism": "The water makes the step visible.",
                "emotionalHeart": "Keen is loved while he is scared.",
            },
            "gagClocks": [],
        },
        "dramaticBeat": "Keen faces the water.",
        "audienceBefore": "Keen is supported.",
        "audienceAfter": "Keen tries to be brave.",
        "beatOwner": "Keen",
        "performanceFreedom": "Allow small eye and breath movement.",
        "performanceArc": "Supported to frightened to trying.",
        "physicalCauseAndEffect": "The water draws his gaze.",
        "cameraBehaviour": "A close shot favours Keen.",
        "timingAndRhythm": "Look, swallow, hold.",
        "landingBreath": "Hold the quiet aftermath.",
        "directionDensity": "guided",
        "shotPlan": [{
            "shotNumber": 1,
            "purpose": "Make the water feel large.",
            "framingLensAndCamera": "Medium shot at child eye height.",
            "causalAction": "Keen looks to the water.",
            "observablePerformance": "Keen tries to stay steady.",
            "compositionLightAndMaterials": "Warm pier light.",
            "landingImage": "Keen remains beside the water.",
            "dialogueLineIndexes": [],
            "dialogueDirections": [],
        }],
        "timingBeats": [],
        "witnessStagingSides": [],
        "stagePlan": [{
            "stageNumber": 1,
            "beatIds": ["3.B2"],
            "purpose": "Borrowed courage",
            "initialOrCarriedState": "Keen is beside the boat.",
            "cause": "The water looks large.",
            "primaryEvent": "Keen looks out.",
            "emotionOrCameraAnalysis": "Stay close.",
            "observableEndState": "Keen holds beside the water.",
        }],
        "geography": ["Keen stands on the pier."],
        "attributeOwnership": [],
        "environmentContract": [],
        "referenceContract": [{
            "assetTag": "@图1",
            "role": "opening_frame",
            "controls": "opening composition and carried state only",
            "scope": "continuity",
        }],
        "openingCarriedState": "Keen is beside the boat.",
        "consistencyContract": ["Keen stays on the pier."],
        "audioContract": "No dialogue.",
        "continuityFinish": "Keen stays beside the water.",
        "surgicalSafeguards": [],
    }
    prompt = D.compile_animation_provider_prompt(shot, direction)

    assert "@图1 owns" not in prompt
    assert "@图1 is the first frame." in prompt
    assert "exclude later action and redesign" in prompt


def test_animation_location_controls_line_is_normalized_to_defines():
    shot = {
        "shotId": "3.B2.S1",
        "charactersInFrame": ["Keen"],
        "durationSec": 9,
        "dialogueLines": [],
    }
    direction = {
        "shotId": "3.B2.S1",
        "durationSec": 9,
        "taskMode": "reference-to-video",
        "pacingMode": "storyline",
        "generationGoal": "Keen looks out at the water.",
        "deliveryPlan": "Keep the beat simple.",
        "creativeTranslation": {
            "interpretation": {
                "mechanism": "The water makes the step visible.",
                "emotionalHeart": "Keen is loved while he is scared.",
            },
            "gagClocks": [],
        },
        "dramaticBeat": "Keen faces the water.",
        "audienceBefore": "Keen is supported.",
        "audienceAfter": "Keen tries to be brave.",
        "beatOwner": "Keen",
        "performanceFreedom": "Allow small eye and breath movement.",
        "performanceArc": "Supported to frightened to trying.",
        "physicalCauseAndEffect": "The water draws his gaze.",
        "cameraBehaviour": "A close shot favours Keen.",
        "timingAndRhythm": "Look, swallow, hold.",
        "landingBreath": "Hold the quiet aftermath.",
        "directionDensity": "guided",
        "shotPlan": [{
            "shotNumber": 1,
            "purpose": "Make the water feel large.",
            "framingLensAndCamera": "Medium shot at child eye height.",
            "causalAction": "Keen looks to the water.",
            "observablePerformance": "Keen tries to stay steady.",
            "compositionLightAndMaterials": "Warm pier light.",
            "landingImage": "Keen remains beside the water.",
            "dialogueLineIndexes": [],
            "dialogueDirections": [],
        }],
        "timingBeats": [],
        "witnessStagingSides": [],
        "stagePlan": [{
            "stageNumber": 1,
            "beatIds": ["3.B2"],
            "purpose": "Borrowed courage",
            "initialOrCarriedState": "Keen is beside the boat.",
            "cause": "The water looks large.",
            "primaryEvent": "Keen looks out.",
            "emotionOrCameraAnalysis": "Stay close.",
            "observableEndState": "Keen holds beside the water.",
        }],
        "geography": ["Keen stands on the pier."],
        "attributeOwnership": [],
        "environmentContract": [],
        "referenceContract": [{
            "assetTag": "@图4",
            "role": "location",
            "controls": "the island shore, dock, boat-world material language and daylight",
            "scope": "canon",
        }],
        "openingCarriedState": "Keen is beside the boat.",
        "consistencyContract": ["Keen stays on the pier."],
        "audioContract": "No dialogue.",
        "continuityFinish": "Keen stays beside the water.",
        "surgicalSafeguards": [],
    }
    prompt = D.compile_animation_provider_prompt(shot, direction)

    assert "@图4 controls" not in prompt
    assert "@图1 defines scene/layout/light only" in prompt


def test_animation_department_candidate_persists_watch_preflight():
    preflight = {
        "verdict": "PASS",
        "score": 9.75,
        "maximum": 10,
        "findings": [],
        "seedanceAuthoring": {"normalizedScore": 10, "firingFloor": 9.5},
    }
    candidate = R._department_candidate(
        "animation", {"providerPrompt": "Ready prompt."},
        {"animationPreflight": preflight})
    assert candidate["preflight"] == preflight


def test_animation_recompile_refreshes_watch_preflight_source():
    from pathlib import Path
    body = Path(R.__file__).read_text(encoding="utf-8")
    assert 'candidate["preflight"] = _animation_preflight_summary(' in body


def test_dialogue_is_emitted_inside_beat_with_delivery_and_full_beat_hold():
    cue = D.emission.dialogue_cues([{
        "speaker": "Performer", "exactText": "Nailed it.",
        "delivery": "[confident] Nailed it.", "startSec": 1, "endSec": 2,
    }], duration_sec=4)[0]
    line = D.emission.dialogue_placement_line(
        cue, direction="with contained confidence")
    assert "Performer, with contained confidence: {Nailed it.}" in line
    assert "pose holds a full beat after the line ends" in line


def test_human_working_prompt_derives_trace_from_approved_contracts_only_when_explicit():
    primary = "Fuzzby hits the leaf, rebounds upright and holds a proud wobbling pose."
    ending = "Fuzzby hovers proudly while Zenny watches."
    shot = {
        "comedyContractsApproved": [{
            "beatCode": "1.B1", "mode": "BIG", "setup": "Fuzzby enters too fast.",
            "disruption": "The leaf snaps him upright.",
            "hold": "Hold the proud wobble.", "recoveryHoldSec": 2.2,
            "button": "His body disproves the boast.",
        }],
        "storyboardStagePlanApproved": [{
            "stageNumber": 1, "beatIds": ["1.B1"], "primaryEvent": primary,
            "observableEndState": ending,
        }],
        "visualPayoff": ending,
        "dialogueLines": [{"exactText": "Nailed it."}],
    }
    prompt = (f"Action/Expression: {primary} Physics: Fuzzby's sideways momentum depresses "
              f"the leaf; the leaf bends, stores force, then snaps him upright. Hold: 2.2s — "
              f"Hold the proud wobble. End state: {ending}")

    strict = D.creative_translation_report(shot, {"providerPrompt": prompt})
    assert strict["ready"] is False
    assert strict["derivedFromApprovedContracts"] is False

    working = D.creative_translation_report(shot, {
        "providerPrompt": prompt,
        "deriveCreativeTranslationFromApproved": True,
    })
    assert working["ready"] is True
    assert working["compiledGagBeatCodes"] == ["1.B1"]
    assert working["derivedFromApprovedContracts"] is True


def test_animation_reads_missing_beat_contracts_only_from_exact_approved_storyboard(tmp_path,
                                                                                    monkeypatch):
    monkeypatch.setattr(R, "ROOT", tmp_path)
    storyboard_shot = {"shotId": "S1.SH1", "beatIds": ["1.B1"]}
    storyboard = {
        "approvalState": "approved", "shots": [storyboard_shot],
        "beats": [{
            "beatId": "1.B1",
            "comedyContract": {"mode": "SMALL", "mechanism": "deadpan contrast"},
            "emotionContract": {"owner": "Fuzzby", "exitState": "quietly exposed"},
        }],
    }
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps(storyboard), encoding="utf-8")
    card_hash = hashlib.sha256(json.dumps(
        storyboard_shot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    pkg = {"sourceStoryboard": {
        "path": str(path), "md5": hashlib.md5(path.read_bytes()).hexdigest(),
        "creativeCardHashes": {"S1.SH1": card_hash},
    }}
    shot = {"shotId": "S1.SH1"}

    view = R._shot_creative_contract_view(pkg, shot, "1", "Ep1")
    assert view["comedyContractsApproved"][0]["mechanism"] == "deadpan contrast"
    assert view["emotionContractsApproved"][0]["exitState"] == "quietly exposed"
    assert "comedyContractsApproved" not in shot

    pkg["sourceStoryboard"]["md5"] = "stale"
    assert R._shot_creative_contract_view(pkg, shot, "1", "Ep1") is shot
