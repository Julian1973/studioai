import json
import pathlib

import pytest

import cb_safety
import cb_render as render


TEST_CANON_DIGEST = "c" * 64


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
        "referenceSlots": {},
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
    work["approved"] = {
        "outcome": "approved",
        "output": output,
        "packageRevision": package["revision"],
        "inputSignature": render._department_input_signature(
            package, stage, shot_id, "1", "Ep1"),
    }
    return work["approved"]


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


def test_animation_approval_carries_forward_and_tracks_its_own_graph(
        tmp_path, monkeypatch):
    package, shot, _ = _pkg(tmp_path)
    monkeypatch.setattr(render, "_keyframe_input_signature",
                        lambda *args, **kwargs: {
                            "cardHash": "card-v1",
                            "canonProfileDigest": TEST_CANON_DIGEST})
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


def test_pending_scene_look_does_not_disable_current_approved_plate(
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
    look_work["approved"] = {
        "output": {"providerPrompt": "approved environment prompt with enough production detail"},
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
    assert state["status"] == "awaiting"
    assert state["current"] is True
    assert state["approved"]["path"] == str(plate)
