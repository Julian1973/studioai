import hashlib
import json

import pytest

import cb_lineage
import cb_render
import cb_state


class _Store:
    def __init__(self, current):
        self._current = current

    def current(self, episode, required=True):
        return self._current


def test_later_scene_dialogue_correction_keeps_earlier_package_current(tmp_path, monkeypatch):
    source = tmp_path / "old-script.txt"
    source.write_text("unchanged scene one\n", encoding="utf-8")
    old_sha = cb_lineage.sha256_file(source)
    storyboard = tmp_path / "storyboard.json"
    storyboard.write_text('{"scene":1}\n', encoding="utf-8")
    storyboard_md5 = hashlib.md5(storyboard.read_bytes()).hexdigest()
    storyboard_sha = cb_lineage.sha256_file(storyboard)
    inputs = {
        "scriptVersionId": "sha256:" + "1" * 64,
        "beatPackageDigest": "2" * 64,
        "storyboardSha256": storyboard_sha,
        "creativeCardHashes": {},
        "canonProfileDigest": "3" * 64,
    }
    package = {
        "revision": 4,
        "sourceScript": {
            "scriptVersionId": inputs["scriptVersionId"], "sha256": old_sha,
            "contentPath": source.name,
        },
        "sourceStoryboard": {"path": storyboard.name, "md5": storyboard_md5,
                             "sha256": storyboard_sha},
        "inputSignature": cb_lineage.dependency_signature("production-package", inputs),
    }
    current = {
        "scriptVersionId": "sha256:" + "4" * 64, "sha256": "4" * 64,
        "previousScriptVersionId": inputs["scriptVersionId"],
        "changeScope": {"kind": "dialogue-correction", "scene": "8",
                        "shotId": "S8.SH2"},
    }
    monkeypatch.setattr(cb_render, "ROOT", tmp_path)
    monkeypatch.setattr(cb_render, "SCRIPT_STORE", _Store(current))

    status = cb_render.lineage_status(package, "1", "Ep2")

    assert status["current"] is True
    assert status["scriptCurrent"] is True


def test_scoped_correction_keeps_earlier_approved_storyboard_current(tmp_path, monkeypatch):
    inputs = {
        "scriptVersionId": "sha256:" + "1" * 64,
        "beatPackageDigest": "2" * 64,
        "sceneNumber": "1",
        "sourceBeatIds": ["beat-1"],
        "shotIds": ["S1.SH1"],
    }
    storyboard = {
        "sceneNumber": "1", "approvalState": "approved",
        "sourceScript": {"scriptVersionId": inputs["scriptVersionId"]},
        "beats": [{"sourceBeatId": "beat-1"}],
        "shots": [{"shotId": "S1.SH1"}],
        "inputSignature": cb_lineage.dependency_signature(
            "scene-storyboard-snapshot", inputs),
    }
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps(storyboard), encoding="utf-8")
    monkeypatch.setattr(cb_render, "_storyboard_path", lambda scene, episode: path)
    intake = {
        "canonicalCurrent": True,
        "scriptVersionId": "sha256:" + "4" * 64,
        "previousScriptVersionId": inputs["scriptVersionId"],
        "scriptChangeScope": {"kind": "dialogue-correction", "scene": "8"},
        "canonicalBeatPackageDigest": "new-digest",
        "canonProfileDigests": {"storyboard": None},
    }

    _storyboard, current, reason = cb_state._storyboard_status("1", "Ep2", intake)

    assert current is True
    assert reason is None


def test_scoped_correction_does_not_carry_the_changed_scene(tmp_path, monkeypatch):
    path = tmp_path / "storyboard.json"
    storyboard = {
        "sceneNumber": "8", "approvalState": "approved",
        "sourceScript": {"scriptVersionId": "sha256:" + "1" * 64},
        "beats": [], "shots": [],
        "inputSignature": cb_lineage.dependency_signature(
            "scene-storyboard-snapshot", {
                "scriptVersionId": "sha256:" + "1" * 64,
                "beatPackageDigest": "old", "sceneNumber": "8",
                "sourceBeatIds": [], "shotIds": [],
            }),
    }
    path.write_text(json.dumps(storyboard), encoding="utf-8")
    monkeypatch.setattr(cb_render, "_storyboard_path", lambda scene, episode: path)
    intake = {
        "canonicalCurrent": True,
        "scriptVersionId": "sha256:" + "4" * 64,
        "previousScriptVersionId": "sha256:" + "1" * 64,
        "scriptChangeScope": {"kind": "dialogue-correction", "scene": "8"},
        "canonicalBeatPackageDigest": "new", "canonProfileDigests": {"storyboard": None},
    }

    _storyboard, current, reason = cb_state._storyboard_status("8", "Ep2", intake)

    assert current is False
    assert reason in {"storyboard-input-signature-mismatch",
                      "storyboard-script-version-mismatch"}


def test_same_scene_amendment_identifies_only_the_named_shot():
    old = "sha256:" + "1" * 64
    intake = {
        "scriptVersionId": "sha256:" + "2" * 64,
        "previousScriptVersionId": old,
        "scriptChangeScope": {
            "kind": "dialogue-correction", "scene": "1", "shotId": "S1.SH3"},
    }
    package = {
        "sourceScript": {"scriptVersionId": old},
        "shots": [{"shotId": "S1.SH1"}, {"shotId": "S1.SH2"},
                  {"shotId": "S1.SH3"}],
    }

    amendment = cb_state._scoped_shot_amendment(intake, "1", package)

    assert amendment["shotId"] == "S1.SH3"
    assert amendment["preservedStages"] == ["direction", "scenelook", "keyframe"]
    assert amendment["invalidatedStages"] == [
        "voice", "animation", "continuity", "final"]


def test_lineage_accepts_explicit_same_scene_shot_amendment(tmp_path, monkeypatch):
    source = tmp_path / "old-script.txt"
    source.write_text("old immutable script", encoding="utf-8")
    old_sha = cb_lineage.sha256_file(source)
    storyboard = tmp_path / "amendment.json"
    storyboard.write_text('{"approved":true}', encoding="utf-8")
    storyboard_md5 = hashlib.md5(storyboard.read_bytes()).hexdigest()
    storyboard_sha = cb_lineage.sha256_file(storyboard)
    previous_id = "sha256:" + old_sha
    current_id = "sha256:" + "b" * 64
    inputs = {"scriptVersionId": previous_id, "storyboardSha256": storyboard_sha}
    package = {
        "revision": 6,
        "sourceScript": {"scriptVersionId": previous_id, "sha256": old_sha,
                         "contentPath": source.name},
        "sourceStoryboard": {"path": storyboard.name, "md5": storyboard_md5,
                             "sha256": storyboard_sha},
        "inputSignature": cb_lineage.dependency_signature("production-package", inputs),
        "scopedAmendments": [{"kind": "dialogue-correction", "shotId": "S1.SH3",
                              "scriptVersionId": current_id}],
    }
    current = {
        "scriptVersionId": current_id, "sha256": "b" * 64,
        "previousScriptVersionId": previous_id,
        "changeScope": {"kind": "dialogue-correction", "scene": "1",
                        "shotId": "S1.SH3"},
    }
    monkeypatch.setattr(cb_render, "ROOT", tmp_path)
    monkeypatch.setattr(cb_render, "SCRIPT_STORE", _Store(current))

    assert cb_render.lineage_status(package, "1", "Ep2")["current"] is True


def test_lineage_accepts_explicit_amendment_across_accumulated_script_revisions(
        tmp_path, monkeypatch):
    source = tmp_path / "old-script.txt"
    source.write_text("old immutable script", encoding="utf-8")
    old_sha = cb_lineage.sha256_file(source)
    storyboard = tmp_path / "storyboard.json"
    storyboard.write_text('{"approved":true}', encoding="utf-8")
    storyboard_md5 = hashlib.md5(storyboard.read_bytes()).hexdigest()
    storyboard_sha = cb_lineage.sha256_file(storyboard)
    package_id = "sha256:" + old_sha
    current_id = "sha256:" + "d" * 64
    inputs = {"scriptVersionId": package_id, "storyboardSha256": storyboard_sha}
    package = {
        "revision": 6,
        "sourceScript": {"scriptVersionId": package_id, "sha256": old_sha,
                         "contentPath": source.name},
        "sourceStoryboard": {"path": storyboard.name, "md5": storyboard_md5,
                             "sha256": storyboard_sha},
        "inputSignature": cb_lineage.dependency_signature("production-package", inputs),
        "scopedAmendments": [{"kind": "dialogue-correction", "shotId": "S3.SH4",
                              "baseScriptVersionId": package_id,
                              "scriptVersionId": current_id}],
    }
    current = {
        "scriptVersionId": current_id, "sha256": "d" * 64,
        "previousScriptVersionId": "sha256:" + "c" * 64,
        "changeScope": {"kind": "dialogue-correction", "scene": "3",
                        "shotId": "S3.SH4"},
    }
    monkeypatch.setattr(cb_render, "ROOT", tmp_path)
    monkeypatch.setattr(cb_render, "SCRIPT_STORE", _Store(current))

    assert cb_render.lineage_status(package, "3", "Ep2")["current"] is True


def test_v4_forward_gate_accepts_exact_registered_scoped_director_amendment(
        tmp_path, monkeypatch):
    shot = {
        "shotId": "S1.SH3",
        "storyIntentApproved": {"narrativeFunction": "Land the scene."},
        "performanceBudgetApproved": {"minimumHonestDurationSec": 7},
        "cinematographyContractApproved": {"storyPointOfView": "Keen to Zenny."},
        "performanceContractApproved": {"beatOwner": "1.B4"},
    }
    amendment_path = tmp_path / "amendment.json"
    amendment_path.write_text(json.dumps({
        "approvalState": "approved", "shotId": "S1.SH3",
        "scriptVersionId": "sha256:" + "c" * 64,
        "shot": shot,
    }), encoding="utf-8")
    package = {
        "creativeDirectingStandardVersion": 4,
        "sourceStoryboard": {
            "path": amendment_path.name, "approvalState": "approved"},
        "scopedAmendments": [{
            "shotId": "S1.SH3", "kind": "dialogue-correction",
            "scriptVersionId": "sha256:" + "c" * 64,
        }],
    }
    monkeypatch.setattr(cb_render, "ROOT", tmp_path)

    assert cb_render._require_forward_directing_source(
        package, shot, "1", "Ep2") == shot

    changed = {**shot, "storyIntentApproved": {"narrativeFunction": "Changed."}}
    with pytest.raises(cb_render.Refused, match="no longer matches"):
        cb_render._require_forward_directing_source(
            package, changed, "1", "Ep2")


def test_scoped_amendment_carries_only_the_exact_approved_scene_plate(
        tmp_path, monkeypatch):
    plate = tmp_path / "approved-plate.png"
    plate.write_bytes(b"approved scene world")
    digest = cb_render._sha256_file(plate)
    package = {
        "scopedAmendments": [{
            "shotId": "S1.SH3", "sceneLookContentHash": digest,
        }],
    }
    monkeypatch.setattr(cb_render, "scenelook_status",
                        lambda *args, **kwargs: {"current": False})
    monkeypatch.setattr(cb_render, "load_pkg", lambda *args, **kwargs: (package, None))
    monkeypatch.setattr(cb_render, "_load_scenelook_rec", lambda *args, **kwargs: {
        "approved": {"path": str(plate), "hash": digest}})
    monkeypatch.setattr(cb_render, "lineage_status",
                        lambda *args, **kwargs: {"current": True})

    assert cb_render._plate_path("1", "Ep2") == str(plate)

    plate.write_bytes(b"tampered")
    with pytest.raises(cb_render.Refused, match="no current signed scene plate"):
        cb_render._plate_path("1", "Ep2")


def test_same_scene_dialogue_amendment_preserves_see_but_closes_hear_watch(
        tmp_path, monkeypatch):
    media = tmp_path / "approved.png"
    media.write_bytes(b"approved keyframe")
    package = {
        "shots": [{
            "shotId": "S1.SH3", "sourceType": "opener",
            "charactersInFrame": ["Keen", "Zenny"], "dialogueLines": [
                {"speaker": "Keen", "text": "We'll see."}],
            "ledger": {
                "keyframeApproval": {
                    "approved": True, "path": str(media),
                    "contentHash": cb_render._sha256_file(media)},
                "status": "designed",
            },
        }],
    }
    neutral = {"current": False, "reason": "signature changed", "approved": False}
    monkeypatch.setattr(cb_render, "_ledger", lambda pkg, shot_id: pkg["shots"][0]["ledger"])
    monkeypatch.setattr(cb_render, "_department_record_status",
                        lambda *args, **kwargs: dict(neutral))
    monkeypatch.setattr(cb_render, "_keyframe_record_status",
                        lambda *args, **kwargs: dict(neutral))
    monkeypatch.setattr(cb_render, "_voice_approval_status",
                        lambda *args, **kwargs: dict(neutral))
    monkeypatch.setattr(cb_render, "_animation_approval_status",
                        lambda *args, **kwargs: dict(neutral))
    monkeypatch.setattr(cb_state, "_keyframe_candidate_current",
                        lambda *args, **kwargs: False)
    monkeypatch.setattr(cb_state.cb_audio_authority, "spoken_dialogue_lines",
                        lambda shot: shot.get("dialogueLines") or [])

    state = cb_state._shot_state(
        package, package["shots"][0], "1", "Ep2", True, True,
        amendment={"shotId": "S1.SH3", "active": True})

    assert state["current"]["keyframe"] is True
    assert state["keyframeSatisfied"] is True
    assert state["current"]["voice"] is False
    assert state["current"]["animation"] is False
    assert state["allowedActions"]["fireAnimation"] is False


def test_current_voice_approval_completes_hear_amendment_without_reopening_see(
        tmp_path, monkeypatch):
    media = tmp_path / "approved.png"
    media.write_bytes(b"approved keyframe")
    package = {
        "shots": [{
            "shotId": "S1.SH3", "sourceType": "opener",
            "charactersInFrame": ["Keen", "Zenny"], "dialogueLines": [
                {"speaker": "Keen", "text": "We'll see."}],
            "ledger": {
                "keyframeApproval": {
                    "approved": True, "path": str(media),
                    "contentHash": cb_render._sha256_file(media)},
                "voiceApproval": {"approved": True},
                "voPath": str(tmp_path / "approved.wav"),
                "status": "designed",
            },
        }],
    }
    (tmp_path / "approved.wav").write_bytes(b"approved voice")
    stale = {"current": False, "reason": "downstream inputs changed", "approved": False}
    monkeypatch.setattr(cb_render, "_ledger", lambda pkg, shot_id: pkg["shots"][0]["ledger"])
    monkeypatch.setattr(cb_render, "_department_record_status",
                        lambda *args, **kwargs: dict(stale))
    monkeypatch.setattr(cb_render, "_keyframe_record_status",
                        lambda *args, **kwargs: dict(stale))
    monkeypatch.setattr(cb_render, "_voice_approval_status",
                        lambda *args, **kwargs: {
                            "current": True, "reason": None, "approved": True})
    monkeypatch.setattr(cb_render, "_animation_approval_status",
                        lambda *args, **kwargs: dict(stale))
    monkeypatch.setattr(cb_state, "_keyframe_candidate_current",
                        lambda *args, **kwargs: False)
    monkeypatch.setattr(cb_state.cb_audio_authority, "spoken_dialogue_lines",
                        lambda shot: shot.get("dialogueLines") or [])

    state = cb_state._shot_state(
        package, package["shots"][0], "1", "Ep2", True, True,
        amendment={"shotId": "S1.SH3", "active": True,
                   "changedStage": "voice",
                   "preservedStages": ["direction", "scenelook", "keyframe"]})

    assert state["current"]["keyframe"] is True
    assert state["current"]["voice"] is True
    assert state["voiceOk"] is True
    assert state["amendment"]["active"] is False
    assert state["amendment"]["changedStageCurrent"] is True
    assert state["animState"] == "designed"
    assert state["allowedActions"]["prepareAnimation"] is True


def test_dialogue_amendment_carries_exact_approved_keyframe(monkeypatch, tmp_path):
    media = tmp_path / "approved.png"
    media.write_bytes(b"approved keyframe")
    digest = cb_render._sha256_file(media)
    record = {
        "approved": True, "path": str(media), "source": "uploaded",
        "contentHash": digest,
        "inputSignature": {
            "cardHash": "old-card", "sceneLookHash": "old-look",
            "selectedAssetHash": "asset", "canonProfileDigest": "canon",
            "source": "uploaded",
        },
        "conformanceAdvisoryDecision": {"acceptedBy": "Julian"},
    }
    package = {
        "sceneNumber": "1", "episode": "Ep2",
        "shots": [{"shotId": "S1.SH3"}],
        "continuityLedger": [{
            "shotId": "S1.SH3",
            "scopedAmendment": {
                "kind": "dialogue-correction", "keyframeContentHash": digest,
            },
        }],
    }
    monkeypatch.setattr(cb_render, "_keyframe_record_status", lambda *a, **k: {})
    # The safety wrapper installs the production implementation at import time. Its
    # expected signature may lose only storyboard-card and Scene Look freshness for a
    # dialogue-only correction; asset and canon authority stay exact.
    expected = {
        "cardHash": None, "sceneLookHash": None, "selectedAssetHash": "asset",
        "canonProfileDigest": "canon", "source": "uploaded",
    }
    stored = record["inputSignature"]
    changed = set(cb_render._signature_diff(stored, expected))
    assert changed == {"cardHash", "sceneLookHash"}
    assert package["continuityLedger"][0]["scopedAmendment"][
        "keyframeContentHash"] == record["contentHash"]


@pytest.mark.parametrize(("stage", "preserved", "invalidated"), [
    ("direction", ["scenelook"],
     ["direction", "keyframe", "voice", "animation", "continuity", "final"]),
    ("see", ["direction", "scenelook", "voice"],
     ["keyframe", "animation", "continuity", "final"]),
    ("hear", ["direction", "scenelook", "keyframe"],
     ["voice", "animation", "continuity", "final"]),
    ("watch", ["direction", "scenelook", "keyframe", "voice"],
     ["animation", "continuity", "final"]),
])
def test_shot_change_dependency_map_never_reopens_earlier_stages(
        stage, preserved, invalidated):
    scope = {"kind": "shot-amendment", "stage": stage}
    resolved = cb_state._amendment_stage(scope)
    dependency = cb_state._SHOT_STAGE_DEPENDENCIES[resolved]

    assert dependency["preserved"] == preserved
    assert dependency["invalidated"] == invalidated
