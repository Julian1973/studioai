"""Focused proofs for the live department workers (all zero-provider-call)."""
import hashlib
import json

import pytest

import cb_departments as D
import cb_render as R
import cb_safety


def _locked():
    return [{"speaker": "FUZZBY", "exactText": "Nailed it."}]


def test_every_studio_department_loads_a_real_runtime_skill_contract():
    people = D.roster()
    assert len(people) == 7
    assert all(p["loaded"] for p in people)
    assert {p["worker"] for p in people} >= {
        "Director", "Cinematographer / DP", "Voice Director",
        "Seedance Production Director", "Director Review / Continuity Supervisor",
        "Post Supervisor"}


def test_voice_director_may_act_but_not_rewrite_locked_words():
    valid = D.VoiceDirection(
        shotId="S1.SH1", sceneIntention="cover the wobble",
        lines=[D.VoiceLineDirection(
            speaker="FUZZBY", exactDialogue="Nailed it.",
            performedText="[nervous] NAILED... it.", dramaticIntention="sell control",
            subtext="the body disagrees", cadenceAndBreath="too bright",
            timingAndBody="after the rebound")])
    assert D.validate_voice_direction(valid, _locked()) is valid

    changed = valid.model_copy(deep=True)
    changed.lines[0].performedText = "[nervous] Totally nailed it."
    with pytest.raises(RuntimeError, match="added, dropped or changed words"):
        D.validate_voice_direction(changed, _locked())


def test_prepare_voice_loads_the_skill_and_stops_at_structured_candidate(monkeypatch):
    seen = {}

    def fake(system, user, schema, **kwargs):
        seen["system"] = system
        return schema(
            shotId="S1.SH1", sceneIntention="cover the wobble",
            lines=[D.VoiceLineDirection(
                speaker="FUZZBY", exactDialogue="Nailed it.",
                performedText="[nervous] Nailed it.", dramaticIntention="sell control",
                subtext="the body disagrees", cadenceAndBreath="too bright",
                timingAndBody="after the rebound")])

    monkeypatch.setattr(D.cb_llm, "structured", fake)
    out = D.prepare_voice({"shotId": "S1.SH1"}, _locked(), log=lambda *a, **k: None)
    assert out.lines[0].performedText == "[nervous] Nailed it."
    assert "Runtime worker contract — Voice Director" in seen["system"]


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
                primaryEvent="His planted paw loads the plank and the deck kicks back.",
                observableEndState="He holds a readable off-balance silhouette.",
                emotionOrCameraAnalysis="The restrained push lets the private flinch land.")],
            referenceContract=[D.ReferenceDirection(
                assetTag="@Image1", role="opening_frame",
                controls="Exact opening state and composition", scope="continuity")],
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
    out = D.prepare_animation(
        {"shot": {"shotId": "S1.SH1", "durationSec": 8},
         "referenceSlots": {"@Image1": "opening frame"}},
        ["opening.png"], log=lambda *a, **k: None)
    assert len(out.shotPlan) == 1
    assert len(out.stagePlan) == 1
    assert out.pacingMode == "storyline"
    assert out.durationSec == 8
    assert out.referenceContract[0].assetTag == "@Image1"
    assert "Runtime worker contract — Seedance Production Director" in seen["system"]
    assert "Keep every spoken word out of providerPrompt" in seen["user"]
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
        "providerPrompt": "Action/Expression: " + provider_action,
        "creativeTranslation": {
            "gagClocks": [{
                "beatCode": "1.B1", "mode": "BIG", "setup": approved["setup"],
                "anticipation": "The leaf bends visibly before release.",
                "impact": approved["disruption"],
                "reaction": "Zenny gives one restrained look.",
                "recoveryHold": approved["hold"], "recoveryHoldSec": 1.0,
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


def test_human_working_prompt_derives_trace_from_approved_contracts_only_when_explicit():
    primary = "Fuzzby hits the leaf, rebounds upright and holds a proud wobbling pose."
    ending = "Fuzzby hovers proudly while Zenny watches."
    shot = {
        "comedyContractsApproved": [{
            "beatCode": "1.B1", "mode": "BIG", "setup": "Fuzzby enters too fast.",
            "disruption": "The leaf snaps him upright.",
            "hold": "Hold the proud wobble.", "button": "His body disproves the boast.",
        }],
        "storyboardStagePlanApproved": [{
            "stageNumber": 1, "beatIds": ["1.B1"], "primaryEvent": primary,
            "observableEndState": ending,
        }],
        "visualPayoff": ending,
        "dialogueLines": [{"exactText": "Nailed it."}],
    }
    prompt = f"Action/Expression: {primary} End state: {ending}"

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
