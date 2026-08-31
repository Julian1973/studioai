"""Current specialist-gated production path, end to end with every provider mocked."""
import hashlib
import json
import pathlib

import pytest

import cb_canon
import cb_render as R
from test_golden_path import (world, _approve_animation_direction,
                              _approve_director_review,
                              _cinematography_output,
                              _fixture_reference_contract,
                              _lock_scene_cut,
                              _voice_direction_output,
                              _test_seedance_25_contract)


@pytest.fixture(autouse=True)
def isolated_canon(monkeypatch):
    digests = {name: "c" * 64 for name in (
        "story", "storyboard", "look", "cinematography", "voice",
        "animation", "review", "post")}
    monkeypatch.setattr(cb_canon, "require_locked", lambda *args, **kwargs: {
        "manifestDigest": "m" * 64, "profileDigests": digests})
    monkeypatch.setattr(R.cb_providers, "request_contract", _test_seedance_25_contract)


def _approve_specialist_inputs(pkg):
    revision = 1
    pkg["revision"] = revision
    by_id = {s["shotId"]: s for s in pkg["shots"]}
    for ledger in pkg["continuityLedger"]:
        shot = by_id[ledger["shotId"]]
        for index, line in enumerate(shot.get("dialogueLines") or []):
            occurrence_id = line.get("dialogueOccurrenceId") or (
                f"{shot['shotId']}.dialogue.{index + 1}")
            line["dialogueOccurrenceId"] = occurrence_id
            line["sourceEventId"] = line.get("sourceEventId") or occurrence_id
        ledger["departmentWork"] = {
            "cinematography": {"approved": {
                "packageRevision": revision,
                "output": _cinematography_output(shot)}},
            "voice": {"approved": {
                "packageRevision": revision,
                "output": _voice_direction_output(shot)}},
            "animation": {"approved": {
                "packageRevision": revision,
                "output": _animation_direction_output(shot)}},
        }


def _animation_direction_output(shot):
    duration = int(round(float(shot.get("durationSec") or 6)))
    beat_id = shot.get("beatCode") or "1.B1"
    data = {
        "shotId": shot["shotId"],
        "durationSec": duration,
        "taskMode": "reference-to-video",
        "pacingMode": "storyline",
        "generationGoal": "Deliver the approved production beat with readable cause and effect.",
        "deliveryPlan": "Use the approved stage, references, voice authority, and continuity finish.",
        "creativeTranslation": {
            "interpretation": {
                "jokeOrAche": "The approved fixture beat.",
                "mechanism": "Visible cause creates a readable emotional result.",
                "statusBefore": "The character enters the beat with intent.",
                "statusAfter": "The character exits with the approved handoff state.",
                "audienceProgression": ["Setup", "change", "landing"],
                "emotionalHeart": "The performance makes the story turn legible.",
            },
            "gagClocks": [],
            "generationDesign": {
                "packagingDecision": "single-unit",
                "completeGagArcCount": 0,
                "densityJudgement": "The fixture fits one provider unit.",
                "splitOrNonSplitRationale": "One causal beat is enough for the test.",
                "handoffState": "The approved final frame remains usable.",
            },
        },
        "dramaticBeat": "The approved fixture beat lands cleanly.",
        "audienceBefore": "The audience understands the setup.",
        "audienceAfter": "The audience understands the result.",
        "beatOwner": (shot.get("charactersInFrame") or ["Fuzzby"])[0],
        "performanceFreedom": "Allow micro-expression and secondary motion only.",
        "performanceArc": (
            "The eyes settle before the action, then the shoulders soften after the result."
        ),
        "physicalCauseAndEffect": (
            "The character turns and moves because the visible cause prompts them, then "
            "stops so that the result lands."
        ),
        "cameraBehaviour": shot.get("camera") or (
            "A medium-wide camera tracks the action, then holds the final framing."
        ),
        "timingAndRhythm": "Keep the beat moving while preserving the landing hold.",
        "landingBreath": "Hold the final image long enough to read.",
        "directionDensity": "guided",
        "shotPlan": [{
            "shotNumber": 1,
            "purpose": "Deliver the approved action.",
            "framingLensAndCamera": shot.get("camera") or "Readable framed camera.",
            "causalAction": (
                "The character turns and moves because the visible cause prompts them, then "
                "stops so that the result lands before the reaction."
            ),
            "observablePerformance": (
                "The eyes focus before the move; after it lands, breath and posture soften."
            ),
            "compositionLightAndMaterials": (
                "Layer foreground, midground and background under warm controlled light; "
                "preserve fur texture, contact shadow, scale and materials."
            ),
            "landingImage": shot.get("visualPayoff") or "Approved final state.",
            "dialogueLineIndexes": list(range(
                1, len(shot.get("dialogueLines") or []) + 1)),
            "dialogueDirections": [
                str(line.get("delivery") or "Act the line from the body.")
                for line in (shot.get("dialogueLines") or [])],
            "holdAfterDialogue": not bool(shot.get("dialogueLines")),
            "gagBeatIds": [],
        }],
        "stagePlan": [{
            "stageNumber": 1,
            "beatIds": [beat_id],
            "purpose": "Deliver the approved story event in one readable unit.",
            "initialOrCarriedState": "The approved opening frame establishes the stage.",
            "cause": "The character action begins from the approved physical setup.",
            "primaryEvent": "The character completes the approved causal action.",
            "observableEndState": "The shot lands on the approved describable handoff state.",
            "emotionOrCameraAnalysis": "The camera holds long enough for the performance turn to read.",
        }],
        "geography": [
            "The flower corridor travels frame-left to frame-right at bee height, "
            "with the springy leaf visible on the route."],
        "attributeOwnership": [],
        "environmentContract": [],
        "referenceContract": _fixture_reference_contract(shot),
        "consistencyContract": [
            "Keep identity, character count, scale, props, scene geography, light direction, and camera axis stable."
        ],
        "audioContract": (
            "@Audio1 is the sole source of dialogue, voice, performance, timing and silence."
            if shot.get("dialogueLines") else "No dialogue."),
        "continuityFinish": shot.get("visualPayoff") or "End on the approved describable frame.",
        "providerPrompt": "Temporary fixture prompt until compiled by the deterministic animation compiler.",
    }
    direction = R.cb_departments.AnimationDirection.model_validate(data)
    data = direction.model_dump()
    data["providerPrompt"] = R.cb_departments.compile_animation_provider_prompt(
        shot, direction)
    return data


def _approve_scene_look(tmp, pkg):
    plate = tmp / "engine" / "media" / "EpT_S9_plate.png"
    plate.parent.mkdir(parents=True, exist_ok=True)
    plate.write_bytes(b"CURRENT_PRODUCTION_PATH_PLATE")
    prompt = ("Environment-only warm flower corridor at bee scale, with readable depth, "
              "springy leaves, golden pollen and no characters or text.")
    plate_hash = hashlib.sha256(plate.read_bytes()).hexdigest()
    signature = {"briefHash": hashlib.sha256(prompt.encode()).hexdigest(),
                 "referenceHashes": {}, "plateHash": plate_hash}
    rec = {
        "approved": {"path": str(plate), "hash": plate_hash,
                     "inputSignature": signature, "packageRevision": pkg["revision"],
                     "referencePath": None, "approvedAt": "test", "reviewedBy": "Test"},
        "candidate": None, "history": [],
        "departmentWork": {"look": {"approved": {
            "packageRevision": pkg["revision"], "output": {"providerPrompt": prompt}},
            "candidate": None, "history": []}},
    }
    rec["departmentWork"]["look"]["approved"]["inputSignature"] = \
        R._department_input_signature(pkg, "look", None, "9", "EpT")
    R._save_scenelook_rec(rec, "9", "EpT")
    rec = R._load_scenelook_rec("9", "EpT")
    rec["approved"]["inputSignature"] = R._scenelook_record_input_signature(
        "9", "EpT", rec["approved"]["path"], None)
    R._save_scenelook_rec(rec, "9", "EpT")


def _sign_specialist_inputs(pkg):
    for shot in pkg["shots"]:
        ledger = R._ledger(pkg, shot["shotId"])
        for stage in ("voice", "cinematography"):
            ledger["departmentWork"][stage]["approved"]["inputSignature"] = \
                R._department_input_signature(pkg, stage, shot["shotId"], "9", "EpT")


def _disclose_and_fire(shot_id):
    _approve_animation_direction(shot_id)
    with pytest.raises(R.Refused, match="SPEND NOT APPROVED"):
        R.fire_shot("9", shot_id, "EpT", candidates=1, log=lambda *a, **k: None)
    pkg, _ = R.load_pkg("9", "EpT")
    token = R._ledger(pkg, shot_id)["pendingSpendAuth"]["token"]
    return R.fire_shot("9", shot_id, "EpT", candidates=1, spend_token=token,
                       log=lambda *a, **k: None)


def test_current_path_reaches_an_approved_master_without_provider_spend(
        world, monkeypatch):
    providers, tmp, pkg_path = world
    monkeypatch.setattr(R, "screen_keyframe_conformance", lambda *args, **kwargs: {
        "status": "pass", "reason": None,
        "review": {"verdict": "pass", "summary": "Test fixture passes."},
    })
    pkg = json.loads(pkg_path.read_text())
    _approve_specialist_inputs(pkg)
    pkg_path.write_text(json.dumps(pkg, indent=1))
    _approve_scene_look(tmp, pkg)
    _sign_specialist_inputs(pkg)
    pkg_path.write_text(json.dumps(pkg, indent=1))

    # Voice is generated shot-by-shot from approved Voice direction, then heard/approved.
    for shot in pkg["shots"]:
        if shot.get("dialogueLines"):
            R.regen_voice_shot("9", shot["shotId"], "EpT", log=lambda *a, **k: None)
            R.approve_voice("9", shot["shotId"], "EpT", reviewed_by="Test",
                            log=lambda *a, **k: None)

    # The opener gets a reviewed keyframe. Relay shots use the prior approved final frame.
    first = pkg["shots"][0]["shotId"]
    R.keyframe_shot("9", first, "EpT", log=lambda *a, **k: None)
    R.select_keyframe_candidate("9", first, "A", "EpT", log=lambda *a, **k: None)
    R.approve_keyframe("9", first, "EpT", reviewed_by="Test",
                       log=lambda *a, **k: None)

    for shot in pkg["shots"]:
        sid = shot["shotId"]
        assert _disclose_and_fire(sid)
        R.approve_shot("9", sid, 1, "EpT", reviewed_by="Test",
                       log=lambda *a, **k: None)
        _approve_director_review("review-animation", sid)

    _lock_scene_cut("9", "EpT")
    master = R.stitch_scene("9", "EpT", log=lambda *a, **k: None)
    assert pathlib.Path(master).exists()
    _approve_director_review("review-final")
    final_pkg, _ = R.load_pkg("9", "EpT")
    assert R.post_status(final_pkg, "9", "EpT")["approved"]["current"] is True
    assert len(providers.voice_calls) == 2
    assert len(providers.image_calls) == 2
    assert len(providers.fire_calls) == 3
    assert [x["prompt"] for x in providers.fire_calls] == [
        R._approved_seedance_prompt(final_pkg, s) for s in final_pkg["shots"]]
