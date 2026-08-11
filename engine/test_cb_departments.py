"""Focused proofs for the live department workers (all zero-provider-call)."""
import hashlib
import json

import pytest

import cb_departments as D
import cb_render as R
import cb_safety


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
    with pytest.raises(RuntimeError, match="omitted dramatic purpose.*casual"):
        D.validate_voice_direction(missing_take_tag_purpose, _locked())


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
    assert "Dialogue placement: Fuzzby: {Nailed it.}" in compiled
    assert "Dialogue placement: Zenny: {Officially nuts!}" in compiled
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
    assert "@Image2 defines only Fuzzby's exact identity and proportions." in compiled
    assert "Do not use its background, pose, composition" in compiled


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
    assert "[Performance Sequence]" in compiled
    assert "[Camera and Shot Plan]" in compiled
    assert "Shot 1: Camera: Medium 40mm, slow motivated push" in compiled
    assert "Action: His paw loads the plank and the deck kicks back" in compiled
    assert "Emotion/Camera Analysis:" not in compiled
    assert "Stage 1: [1.B1]" in compiled
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
    assert "@Image1 is the first frame" in prompt
    assert "@Image1 is the first frame. It defines opening composition and state" in prompt
    assert "Fixed slots: @Image1=opening_frame; @Image2=Fuzzby; @Audio1=audio." in prompt
    assert "Angles: @Image2=one Fuzzby; never extra characters." in prompt
    assert "AUDIO-AUTHORITY: @Audio1 is the sole authority" in prompt
    assert "[Performance Sequence]" in prompt
    assert "[Timestamp Script Storyboard]" not in prompt
    assert "Stage 1: 0-9s" not in prompt
    assert "Hold: 2.2s" in prompt
    assert "Dialogue placement: Fuzzby: {Nailed it.}" in prompt
    assert "Audio cues:" not in prompt
    assert "Physics: Fuzzby's sideways momentum depresses the leaf" in prompt
    assert "Include two readable near-misses before the first impact." in prompt
    assert ("Exactly one Fuzzby and one Zenny throughout; no duplicates of either "
            "character.") in prompt
    assert "@Image2 defines Fuzzby identity/scale; exclude everything else." in prompt
    assert "No music." in prompt
    assert "Hold: 2.2s" in prompt and "approximately 2.2s" not in prompt
    assert len(prompt.split()) <= D.animation_provider_prompt_word_limit(9)


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
    assert "No music." in prompt


def test_render_compaction_never_emits_a_dangling_sentence():
    assert D.emission.compact_complete_sentence(
        "Keep the contact readable, then settle for the lie, while protecting the leaf "
        "recoil and proud recovery in the final composition.",
        max_words=10, context="camera analysis") == (
            "Keep the contact readable, then settle for the lie.")
    with pytest.raises(D.emission.EmissionConformanceError, match="without cutting prose"):
        D.emission.compact_complete_sentence(
            "Keep the leaf recoil and proud recovery visibly readable throughout",
            max_words=5, context="camera analysis")


def test_animation_compiler_emits_every_internal_shot_in_order():
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
    assert prompt.index("Shot 1:") < prompt.index("Shot 2:") < prompt.index("Shot 3:")
    assert "follows slightly late" in prompt
    assert "compresses the flower and loads the springy leaf" in prompt
    assert "one flip and a proud wobbling hover" in prompt


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


def test_animation_reads_missing_beat_contracts_only_from_exact_approved_storyboard(tmp_path):
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
