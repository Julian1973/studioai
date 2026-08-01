"""Current specialist-gated production path, end to end with every provider mocked."""
import hashlib
import json
import pathlib

import pytest

import cb_canon
import cb_render as R
from test_golden_path import (world, _approve_animation_direction,
                              _approve_director_review)


@pytest.fixture(autouse=True)
def isolated_canon(monkeypatch):
    digests = {name: "c" * 64 for name in (
        "story", "storyboard", "look", "cinematography", "voice",
        "animation", "review", "post")}
    monkeypatch.setattr(cb_canon, "require_locked", lambda *args, **kwargs: {
        "manifestDigest": "m" * 64, "profileDigests": digests})


def _approve_specialist_inputs(pkg):
    revision = 1
    pkg["revision"] = revision
    by_id = {s["shotId"]: s for s in pkg["shots"]}
    for ledger in pkg["continuityLedger"]:
        shot = by_id[ledger["shotId"]]
        lines = [{"speaker": line["speaker"],
                  "performedText": line["exactText"]}
                 for line in shot.get("dialogueLines") or []]
        ledger["departmentWork"] = {
            "cinematography": {"approved": {
                "packageRevision": revision,
                "output": {"providerPrompt": shot.get("keyframePrompt") or
                           "Maintain the approved inherited opening frame exactly."}}},
            "voice": {"approved": {
                "packageRevision": revision,
                "output": {"lines": lines}}},
            "animation": {"approved": {
                "packageRevision": revision,
                "output": {"providerPrompt": shot["seedancePrompt"]}}},
        }


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


def test_current_path_reaches_an_approved_master_without_provider_spend(world):
    providers, tmp, pkg_path = world
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
    R.approve_keyframe("9", first, "EpT", reviewed_by="Test",
                       log=lambda *a, **k: None)

    for shot in pkg["shots"]:
        sid = shot["shotId"]
        assert _disclose_and_fire(sid)
        R.approve_shot("9", sid, 1, "EpT", reviewed_by="Test",
                       log=lambda *a, **k: None)
        _approve_director_review("review-animation", sid)

    master = R.stitch_scene("9", "EpT", log=lambda *a, **k: None)
    assert pathlib.Path(master).exists()
    _approve_director_review("review-final")
    final_pkg, _ = R.load_pkg("9", "EpT")
    assert R.post_status(final_pkg, "9", "EpT")["approved"]["current"] is True
    assert len(providers.voice_calls) == 2
    assert len(providers.image_calls) == 1
    assert len(providers.fire_calls) == 3
    assert [x["prompt"] for x in providers.fire_calls] == [
        s["seedancePrompt"] for s in pkg["shots"]]
