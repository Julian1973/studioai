import json
import hashlib
import pathlib

import pytest

import cb_safety
import cb_render as render
from test_golden_path import _current_animation_fixture


TEST_CANON_DIGEST = "c" * 64


def _test_seedance_25_contract(**kwargs):
    duration = int(kwargs["duration"])
    assert 4 <= duration <= 30
    return {
        "providerModelId": "dreamina-seedance-2-5-260628",
        "provider": "byteplus",
        "modelVersion": "2.5-260628",
        "transport": "byteplus-async",
        "mode": "reference-to-video",
        "endpoint": "/api/v3/contents/generations/tasks",
        "resolution": kwargs.get("resolution", "720p"),
        "duration": duration,
        "costRateKey": "seedance_standard_per_sec",
        "capabilityVerifiedAt": "2026-08-04-test-fixture",
        "capabilitySource": "test-fixture",
    }


@pytest.fixture(autouse=True)
def isolated_canon(monkeypatch):
    monkeypatch.setattr(cb_safety.cb_canon, "require_locked", lambda *args, **kwargs: {
        "manifestDigest": "m" * 64,
        "profileDigests": {name: TEST_CANON_DIGEST for name in (
            "story", "storyboard", "look", "cinematography", "voice",
            "animation", "review", "post")},
    })


def _pkg(tmp_path):
    frame = tmp_path / "opening.png"
    frame.write_bytes(b"opening-v1")
    shot = {
        "shotId": "S1.SH1",
        "sourceType": "opener",
        "sourceShotId": None,
        "beatCode": "1.B1",
        "durationSec": 5,
        "dialogueLines": [],
        "referenceSlots": {"@图1": "opening keyframe"},
        "keyframeReferenceSlots": {},
        "keyframePrompt": "approved opening composition",
        "seedancePrompt": "approved motion",
    }
    package = {
        "episode": "Ep1",
        "sceneNumber": "1",
        "revision": 1,
        "validation": {"passed": True},
        "shots": [shot],
        "continuityLedger": [{
            "shotId": "S1.SH1",
            "status": "designed",
            "keyframeApproval": {
                "approved": True,
                "path": str(frame),
                "inputSignature": {"cardHash": "card-v1",
                                   "canonProfileDigest": TEST_CANON_DIGEST},
                "contentHash": render._sha256_file(frame),
                "packageRevision": 1,
                "conformanceScreening": {
                    "status": "pass", "reason": None,
                    "review": {"verdict": "pass"},
                },
            },
            "departmentWork": {},
        }],
    }
    return package, shot, frame


def _approve_department(package, shot_id, stage):
    ledger = render._ledger(package, shot_id)
    work = ledger.setdefault("departmentWork", {}).setdefault(
        stage, {"approved": None, "candidate": None, "history": []})
    output = {
        "providerPrompt": f"approved {stage} provider direction with enough detail"
    }
    if stage == "voice":
        output = {"lines": []}
    elif stage == "animation":
        output = _current_animation_fixture(
            next(item for item in package["shots"] if item["shotId"] == shot_id))
    work["approved"] = {
        "outcome": "approved",
        "output": output,
        "packageRevision": package["revision"],
        "inputSignature": render._department_input_signature(
            package, stage, shot_id, "1", "Ep1"),
    }
    return work["approved"]


def test_seedance_provider_payload_keeps_verbatim_transcript_for_lip_sync():
    prompt = (
        "AUDIO-AUTHORITY: @Audio1 is the sole authority. "
        + render.emission.SINGLE_INSTANCE_DIALOGUE_LOCK
        + "\nSpoken action: Keen: {ACHOO! ... Oh, Ah, Hi Fuzzby}\n"
        + "Fuzzby reacts after \u201cACHOO! ... Oh, Ah, Hi Fuzzby\u201d."
    )
    lines = [{"speaker": "Keen", "exactText": "ACHOO! ... Oh, Ah, Hi Fuzzby"}]

    provider = render._provider_safe_dialogue_prompt(prompt, lines)

    assert provider == prompt
    assert provider.count("ACHOO! ... Oh, Ah, Hi Fuzzby") == 2
    assert "{ACHOO! ... Oh, Ah, Hi Fuzzby}" in provider
    assert "written transcript only to assign the correct speaker and mouth timing" in provider
    assert "Do not synthesize, repeat, dub, echo, layer" in provider
    assert "@Audio1" in provider


def _prepare_department(package, shot_id, stage):
    ledger = render._ledger(package, shot_id)
    work = ledger.setdefault("departmentWork", {}).setdefault(
        stage, {"approved": None, "candidate": None, "history": []})
    output = {
        "providerPrompt": f"prepared {stage} provider direction with enough detail"
    }
    if stage == "voice":
        output = {"lines": []}
    elif stage == "animation":
        output = _current_animation_fixture(
            next(item for item in package["shots"] if item["shotId"] == shot_id))
    work["candidate"] = {
        "output": output,
        "packageRevision": package["revision"],
        "inputSignature": render._department_input_signature(
            package, stage, shot_id, "1", "Ep1"),
    }
    return work["candidate"]


def test_current_prepared_direction_is_operational_without_fake_human_approval(
        tmp_path, monkeypatch):
    package, shot, opening_frame = _pkg(tmp_path)
    monkeypatch.setattr(render, "_keyframe_input_signature",
                        lambda *args, **kwargs: {"cardHash": "card-v1"})
    candidate = _prepare_department(package, shot["shotId"], "cinematography")

    status = render._department_record_status(
        package, shot["shotId"], "cinematography")
    assert status["current"] is True
    assert status["approved"] is False
    assert status["source"] == "prepared"
    assert render._current_department_output(
        package, shot["shotId"], "cinematography") == candidate["output"]

    shot["durationSec"] = 6
    assert not render._department_record_status(
        package, shot["shotId"], "cinematography")["current"]


def test_invalid_voice_contract_is_never_treated_as_current_direction(tmp_path):
    package, shot, _ = _pkg(tmp_path)
    candidate = _prepare_department(package, shot["shotId"], "voice")
    candidate["output"] = {
        "shotId": shot["shotId"],
        "sceneIntention": "invalid provider draft",
        "lines": [{"archetypeId": "invented-voice-archetype"}],
    }

    status = render._department_record_status(
        package, shot["shotId"], "voice", "1", "Ep1")

    assert status["current"] is False
    assert status["reason"].startswith("voice-contract-invalid:")


def test_voice_direction_freshness_excludes_seedance_only_sfx(tmp_path, monkeypatch):
    package, shot, _ = _pkg(tmp_path)
    spoken = {"speaker": "Keen", "exactText": "Hello"}
    sneeze = {"speaker": "Keen", "exactText": "ACHOO!"}
    shot["dialogueLines"] = [sneeze, spoken]
    candidate = _prepare_department(package, shot["shotId"], "voice")
    candidate["output"] = {"shotId": shot["shotId"], "lines": [spoken]}
    checked = {}

    monkeypatch.setattr(
        render.cb_departments.VoiceDirection, "model_validate",
        lambda output: output)
    monkeypatch.setattr(
        render.cb_audio_authority, "route_voice_direction",
        lambda direction, original_lines: (direction, [spoken]))
    monkeypatch.setattr(
        render.cb_departments, "validate_voice_direction",
        lambda direction, lines: checked.setdefault("lines", lines))

    status = render._department_record_status(
        package, shot["shotId"], "voice", "1", "Ep1")

    assert status["current"] is True
    assert checked["lines"] == [spoken]


def test_animation_direction_without_provider_prompt_is_not_current(tmp_path, monkeypatch):
    package, shot, _ = _pkg(tmp_path)
    monkeypatch.setattr(render, "_keyframe_input_signature",
                        lambda *args, **kwargs: {"cardHash": "card-v1",
                                                 "canonProfileDigest": TEST_CANON_DIGEST})
    monkeypatch.setattr(render, "_reference_path_is_approved", lambda path: True)
    candidate = _prepare_department(package, shot["shotId"], "animation")
    candidate["output"].pop("providerPrompt", None)
    candidate["output"]["shotId"] = shot["shotId"]

    status = render._department_record_status(
        package, shot["shotId"], "animation", "1", "Ep1")

    assert status["current"] is False
    assert status["reason"] == "animation-contract-invalid: animation-provider-prompt-missing"


def test_review_evidence_still_requires_a_human_decision(tmp_path):
    package, shot, _ = _pkg(tmp_path)
    work = render._ledger(package, shot["shotId"]).setdefault(
        "departmentWork", {}).setdefault(
            "review-keyframe", {"approved": None, "candidate": None, "history": []})
    work["candidate"] = {
        "output": {"summary": "The actual frame review is ready."},
        "inputSignature": render._department_input_signature(
            package, "review-keyframe", shot["shotId"], "1", "Ep1"),
    }

    status = render._department_record_status(
        package, shot["shotId"], "review-keyframe")
    assert status["current"] is False
    assert status["reason"] == "not-approved"


def test_department_approval_uses_direct_inputs_not_package_revision(tmp_path, monkeypatch):
    package, shot, _ = _pkg(tmp_path)
    monkeypatch.setattr(render, "_keyframe_input_signature",
                        lambda *args, **kwargs: {"cardHash": "card-v1"})
    approval = _approve_department(package, shot["shotId"], "cinematography")

    assert render._department_record_status(
        package, shot["shotId"], "cinematography")["current"]

    package["revision"] = 8
    approval["packageRevision"] = 1
    package["shots"].append({
        "shotId": "S1.SH2", "sourceType": "opener", "sourceShotId": None,
        "beatCode": "1.B2", "durationSec": 4, "dialogueLines": [],
        "referenceSlots": {}, "keyframeReferenceSlots": {},
        "keyframePrompt": "other", "seedancePrompt": "other",
    })
    package["continuityLedger"].append({
        "shotId": "S1.SH2", "status": "designed", "departmentWork": {}})
    assert render._department_record_status(
        package, shot["shotId"], "cinematography")["current"]

    shot["durationSec"] = 6
    assert not render._department_record_status(
        package, shot["shotId"], "cinematography")["current"]


def test_duration_only_visual_change_does_not_stale_human_approved_voice_take(
        tmp_path):
    package, shot, _ = _pkg(tmp_path)
    line = {
        "dialogueOccurrenceId": "dialogue-1", "sourceEventId": "event-1",
        "speaker": "Fuzzby", "exactText": "Nailed it.",
    }
    shot["dialogueLines"] = [line]
    ledger = render._ledger(package, shot["shotId"])
    voice_output = {
        "shotId": shot["shotId"], "sceneIntention": "False confidence lands cleanly.",
        "lines": [{
            **line, "character": "Fuzzby", "exactDialogue": "Nailed it.",
            "performedText": "Nailed it.",
            "dramaticIntention": "Make the listener accept the false victory.",
            "subtext": "He believes the evidence supports him.",
            "cadenceAndBreath": "One easy breath, then misplaced certainty.",
            "timingAndBody": "The line follows the settled proud pose.",
            "archetypeId": "false-triumph-button",
            "performanceQuestions": {
                "intention": "Make the listener accept the false victory.",
                "subtext": "He believes the evidence supports him.",
                "thoughtBefore": "That went exactly as planned.",
                "changeDuring": "Pride settles into certainty.",
                "operativeWords": ["Nailed"],
            },
            "physicalState": "Chest-forward hover after recovery.",
            "emotionalState": {"entry": "Proud", "exit": "Certain"},
            "listener": "Zenny", "bodyVoiceRelationship": "Voice buttons the pose.",
            "previousText": "The leaf has just returned him upright.",
            "startsAtSec": 2.0, "estimatedDurationSec": 1.0,
            "pauseReasons": [], "tagPurposes": {},
            "takeRecipes": [{"recipeId": "A", "label": "Primary",
                              "performedText": "Nailed it.", "primary": True,
                              "takesCount": 2}],
        }],
    }
    work = ledger.setdefault("departmentWork", {}).setdefault("voice", {})
    work["candidate"] = {
        "output": voice_output,
        "inputSignature": render._department_input_signature(
            package, "voice", shot["shotId"], "1", "Ep1"),
    }
    generated = render._approved_voice_lines(package, shot)
    paths = {}
    for field in ("voPath", "voRawPath", "voTimingPath", "voPlacementPath"):
        suffix = ".json" if field == "voPlacementPath" else ".wav"
        path = tmp_path / f"{field}{suffix}"
        path.write_bytes(field.encode())
        ledger[field] = str(path)
        paths[field] = path
    ledger["voGeneratedFrom"] = generated
    expected = render._voice_approval_status(package, shot)["expectedInputSignature"]
    ledger["voiceApproval"] = {
        "approved": True, "path": ledger["voPath"], "inputSignature": expected,
        "contentHash": render._sha256_file(paths["voPath"]),
        "rawContentHash": render._sha256_file(paths["voRawPath"]),
        "timingContentHash": render._sha256_file(paths["voTimingPath"]),
        "placementContentHash": render._sha256_file(paths["voPlacementPath"]),
    }
    assert render._voice_approval_status(package, shot)["current"] is True

    shot["durationSec"] = 12
    assert render._department_record_status(
        package, shot["shotId"], "voice")["current"] is False
    status = render._voice_approval_status(package, shot)
    assert status["current"] is True
    assert status["providerEquivalentContract"] is True


def test_keyframe_approval_survives_revision_but_not_input_or_file_change(
        tmp_path, monkeypatch):
    package, shot, frame = _pkg(tmp_path)
    current = {"cardHash": "card-v1", "canonProfileDigest": TEST_CANON_DIGEST}
    monkeypatch.setattr(
        render, "_keyframe_input_signature",
        lambda *args, **kwargs: dict(current))
    approval = render._ledger(package, shot["shotId"])["keyframeApproval"]

    assert render._keyframe_record_status(package, shot, approval)["current"]
    package["revision"] = 42
    assert render._keyframe_record_status(package, shot, approval)["current"]

    current["cardHash"] = "card-v2"
    assert not render._keyframe_record_status(package, shot, approval)["current"]
    current["cardHash"] = "card-v1"
    frame.write_bytes(b"opening-tampered")
    assert not render._keyframe_record_status(package, shot, approval)["current"]


def test_approved_keyframe_keeps_historical_prompt_after_compiler_only_change(
        tmp_path, monkeypatch):
    package, shot, _ = _pkg(tmp_path)
    historical_prompt = "[Intended Read]\nThe approved opening direction."
    historical_hash = hashlib.sha256(historical_prompt.encode()).hexdigest()
    approval = render._ledger(package, shot["shotId"])["keyframeApproval"]
    approval["inputSignature"] = {
        "cardHash": "card-v1", "canonProfileDigest": TEST_CANON_DIGEST,
        "briefHash": historical_hash,
    }
    approval["promptContract"] = {
        "prompt": historical_prompt, "promptHash": historical_hash,
    }
    monkeypatch.setattr(render, "_keyframe_input_signature", lambda *args, **kwargs: {
        "cardHash": "card-v1", "canonProfileDigest": TEST_CANON_DIGEST,
        "briefHash": "new-compiler-hash",
    })
    monkeypatch.setattr(render, "_keyframe_prompt_contract", lambda *args, **kwargs: {
        "directionContract": {"geography": ["unchanged"]},
    })

    assert render._keyframe_record_status(package, shot, approval)["current"]

    monkeypatch.setattr(
        render, "_keyframe_prompt_contract",
        lambda *args, **kwargs: (_ for _ in ()).throw(render.Refused("direction changed")))
    assert not render._keyframe_record_status(package, shot, approval)["current"]


def test_human_lineage_carry_survives_compiler_brief_change_only(
        tmp_path, monkeypatch):
    package, shot, _ = _pkg(tmp_path)
    approval = render._ledger(package, shot["shotId"])["keyframeApproval"]
    approval["inputSignature"]["briefHash"] = "old-compiler-brief"
    approval["lineageCarryForward"] = {
        "reviewedBy": "Julian",
        "reason": "Keep the signed opening image as visual truth.",
    }
    monkeypatch.setattr(render, "_keyframe_input_signature", lambda *args, **kwargs: {
        "cardHash": "card-v1",
        "canonProfileDigest": TEST_CANON_DIGEST,
        "briefHash": "new-compiler-brief",
    })

    assert render._keyframe_record_status(package, shot, approval)["current"]

    approval["inputSignature"]["cardHash"] = "different-direction"
    assert not render._keyframe_record_status(package, shot, approval)["current"]


def test_animation_approval_carries_forward_and_tracks_its_own_graph(
        tmp_path, monkeypatch):
    package, shot, _ = _pkg(tmp_path)
    monkeypatch.setattr(
        cb_safety.cb_providers, "request_contract", _test_seedance_25_contract)
    monkeypatch.setattr(render, "_keyframe_input_signature",
                        lambda *args, **kwargs: {
                            "cardHash": "card-v1",
                            "canonProfileDigest": TEST_CANON_DIGEST})
    monkeypatch.setattr(render, "_reference_path_is_approved", lambda path: True)
    _approve_department(package, shot["shotId"], "animation")

    take = tmp_path / "take.mp4"
    harvest = tmp_path / "final.png"
    take.write_bytes(b"take-v1")
    harvest.write_bytes(b"final-v1")
    signature = render._animation_generation_signature(
        package, shot, "1", "Ep1", fast=False)
    ledger = render._ledger(package, shot["shotId"])
    ledger.update({
        "status": "approved",
        "approvedTake": str(take),
        "harvestFrame": str(harvest),
        "approval": {
            "approved": True,
            "packageRevision": 1,
            "inputSignature": signature,
            "contentHash": render._sha256_file(take),
            "harvestHash": render._sha256_file(harvest),
        },
    })

    assert render._animation_approval_status(package, shot)["current"]
    package["revision"] = 9
    assert render._animation_approval_status(package, shot)["current"]

    take.write_bytes(b"take-tampered")
    assert not render._animation_approval_status(package, shot)["current"]


def test_external_director_accepted_animation_tracks_contract_anchor_and_content(
        tmp_path, monkeypatch):
    package, shot, opening_frame = _pkg(tmp_path)
    take = tmp_path / "external.mp4"
    harvest = tmp_path / "external-final.png"
    take.write_bytes(b"external-take")
    harvest.write_bytes(b"external-final")
    ledger = render._ledger(package, shot["shotId"])
    monkeypatch.setattr(
        render, "_anchor_for",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("finished-picture approval must not rerun generation gates")))
    input_signature = render._external_import_input_signature(
        package, shot, "1", "Ep1", render._sha256_file(take),
        {"digest": "fixture"})
    ledger.update({
        "status": "approved",
        "approvedTake": str(take),
        "harvestFrame": str(harvest),
        "approval": {
            "approved": True,
            "source": "external-director-accepted",
            "inputSignature": input_signature,
            "contentHash": render._sha256_file(take),
            "harvestHash": render._sha256_file(harvest),
            "provenanceDigest": "fixture",
        },
    })

    assert render._animation_approval_status(package, shot)["current"]
    harvest.write_bytes(b"changed")
    assert not render._animation_approval_status(package, shot)["current"]


def test_current_working_scene_look_feeds_keyframes_without_plate_approval(
        tmp_path, monkeypatch):
    package, _, _ = _pkg(tmp_path)
    plate = tmp_path / "plate.png"
    candidate = tmp_path / "plate-candidate.png"
    plate.write_bytes(b"plate-approved")
    candidate.write_bytes(b"plate-candidate")
    record = {
        "approved": None,
        "candidate": None,
        "history": [],
        "departmentWork": {
            "look": {"approved": None, "candidate": None, "history": []}
        },
    }
    monkeypatch.setattr(render, "load_pkg", lambda *args, **kwargs: (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(render, "_scene_context",
                        lambda *args, **kwargs: {"scene": "1", "story": "unchanged"})
    monkeypatch.setattr(render, "_load_scenelook_rec",
                        lambda *args, **kwargs: record)

    look_work = record["departmentWork"]["look"]
    look_work["candidate"] = {
        "output": {"providerPrompt": "prepared environment prompt with enough production detail"},
        "inputSignature": render._department_input_signature(
            package, "look", None, "1", "Ep1"),
        "packageRevision": 1,
    }
    approved_signature = render._scenelook_record_input_signature(
        "1", "Ep1", str(plate), None)
    record["approved"] = {
        "path": str(plate),
        "hash": render._sha256_file(plate),
        "inputSignature": approved_signature,
    }
    record["candidate"] = {
        "path": str(candidate),
        "hash": render._sha256_file(candidate),
        "inputSignature": render._scenelook_record_input_signature(
            "1", "Ep1", str(candidate), None),
    }

    state = render.scenelook_status("1", "Ep1")
    assert state["status"] == "working"
    assert state["current"] is True
    assert state["active"]["path"] == str(candidate)
    assert state["activeSource"] == "working"
    assert state["approved"]["path"] == str(plate)


def test_human_working_voice_text_overrides_director_recipe(tmp_path, monkeypatch):
    package, shot, _ = _pkg(tmp_path)
    shot["dialogueLines"] = [{
        "dialogueOccurrenceId": "dialogue-1", "sourceEventId": "event-1",
        "speaker": "Fuzzby", "exactText": "I still feel him... every day.",
    }]
    ledger = render._ledger(package, shot["shotId"])
    ledger["workingVoice"] = {"lines": [{
        "dialogueOccurrenceId": "dialogue-1", "sourceEventId": "event-1",
        "speaker": "Fuzzby", "text": "[quietly] I still feel him, every day.",
    }]}
    directed = {
        "shotId": shot["shotId"], "sceneIntention": "Connected memory.",
        "lines": [{
            "dialogueOccurrenceId": "dialogue-1", "sourceEventId": "event-1",
            "speaker": "Fuzzby", "character": "Fuzzby",
            "exactDialogue": "I still feel him... every day.",
            "performedText": "[angry] I still feel him... every day.",
            "dramaticIntention": "Keep the thought connected.", "subtext": "Memory lives on.",
            "cadenceAndBreath": "Quiet and connected.", "timingAndBody": "Stay still.",
            "archetypeId": "held-heart", "performanceQuestions": {
                "intention": "Connect the thought.", "subtext": "Memory lives on.",
                "thoughtBefore": "Say it plainly.", "changeDuring": "She opens.",
                "operativeWords": ["every day"],
            }, "physicalState": "Still.",
            "emotionalState": {"entry": "Held", "exit": "Open"},
            "listener": "Zenny", "bodyVoiceRelationship": "Still body.",
            "previousText": "A quiet look.", "startsAtSec": 1.0,
            "estimatedDurationSec": 2.0, "pauseReasons": [],
            "tagPurposes": [{"tag": "angry", "purpose": "Superseded direction"}],
            "takeRecipes": [{"recipeId": "A", "label": "Primary",
                              "performedText": "[angry] I still feel him... every day.",
                              "primary": True, "takesCount": 1}],
        }],
    }
    ledger.setdefault("departmentWork", {}).setdefault(
        "voice", {"approved": None, "candidate": None, "history": []})["candidate"] = {
        "output": directed,
        "inputSignature": render._department_input_signature(
            package, "voice", shot["shotId"], "1", "Ep1"),
        "packageRevision": package["revision"],
    }

    emitted = render._approved_voice_lines(package, shot)

    assert emitted[0]["text"] == "[quietly] I still feel him, every day."
