import json

import pytest

import cb_rough_cut as rough


def _package(root, take):
    package = {
        "episode": "Ep1",
        "sceneNumber": 1,
        "shots": [{"shotId": "S1.SH1", "durationSec": 29, "purpose": "Open the episode."}],
        "continuityLedger": [{
            "shotId": "S1.SH1",
            "status": "approved",
            "approvedTake": str(take),
        }],
    }
    (root / "Ep1_scene1_production_package.json").write_text(json.dumps(package), encoding="utf-8")


def test_rough_cut_add_is_persistent_and_hash_pinned(tmp_path, monkeypatch):
    monkeypatch.setattr(rough, "OUT", tmp_path)
    take = tmp_path / "take.mp4"
    take.write_bytes(b"approved-v1")
    _package(tmp_path, take)

    state = rough.add_shot("Ep1", "S1.SH1")
    assert state["readyCount"] == 1
    assert state["sequence"][0]["current"] is True
    assert rough.status("Ep1")["sequence"][0]["shotId"] == "S1.SH1"

    take.write_bytes(b"changed-after-selection")
    stale = rough.status("Ep1")
    assert stale["readyCount"] == 0
    assert stale["staleCount"] == 1
    assert stale["sequence"][0]["reason"] == "approved take changed"


def test_rough_cut_refuses_unapproved_or_duplicate_shots(tmp_path, monkeypatch):
    monkeypatch.setattr(rough, "OUT", tmp_path)
    with pytest.raises(ValueError, match="approved animation"):
        rough.add_shot("Ep1", "S1.SH1")

    take = tmp_path / "take.mp4"
    take.write_bytes(b"approved")
    _package(tmp_path, take)
    rough.add_shot("Ep1", "S1.SH1")
    with pytest.raises(ValueError, match="already in"):
        rough.add_shot("Ep1", "S1.SH1")

    state = rough.remove_shot("Ep1", "S1.SH1")
    assert state["sequence"] == []


def test_scene_cut_auto_populates_and_saves_reorder_and_trim(tmp_path, monkeypatch):
    monkeypatch.setattr(rough, "OUT", tmp_path)
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    package = {
        "episode": "Ep1", "sceneNumber": 1,
        "shots": [
            {"shotId": "S1.SH1", "durationSec": 12, "purpose": "Open."},
            {"shotId": "S1.SH2", "durationSec": 10, "purpose": "Land."},
        ],
        "continuityLedger": [
            {"shotId": "S1.SH1", "status": "approved", "approvedTake": str(first)},
            {"shotId": "S1.SH2", "status": "approved", "approvedTake": str(second)},
        ],
    }
    (tmp_path / "Ep1_scene1_production_package.json").write_text(json.dumps(package), encoding="utf-8")

    seeded = rough.scene_status("Ep1", "1")
    assert [entry["shotId"] for entry in seeded["sequence"]] == ["S1.SH1", "S1.SH2"]
    assert seeded["saved"] is False

    saved = rough.save_scene_cut("Ep1", "1", [
        {"shotId": "S1.SH2", "inSec": 1, "outSec": 9, "manualTrim": True},
        {"shotId": "S1.SH1", "inSec": 0, "outSec": 12, "manualTrim": False},
    ], confirm=True)
    assert [entry["shotId"] for entry in saved["sequence"]] == ["S1.SH2", "S1.SH1"]
    assert saved["confirmedCurrent"] is True
    assert saved["totalDurationSec"] == 20

    first.write_bytes(b"changed")
    stale = rough.scene_status("Ep1", "1")
    assert stale["confirmedCurrent"] is False
    assert stale["staleCount"] == 1


def test_scene_cut_refuses_a_trim_that_clips_approved_dialogue(tmp_path, monkeypatch):
    monkeypatch.setattr(rough, "OUT", tmp_path)
    take = tmp_path / "take.mp4"
    take.write_bytes(b"approved")
    package = {
        "episode": "Ep1", "sceneNumber": 1,
        "shots": [{
            "shotId": "S1.SH1", "durationSec": 10, "purpose": "Talk.",
            "dialogueLines": [{
                "dialogueOccurrenceId": "line-1", "speaker": "Bo",
                "exactText": "Hello", "startSec": 2, "endSec": 5,
            }],
        }],
        "continuityLedger": [{
            "shotId": "S1.SH1", "status": "approved", "approvedTake": str(take),
        }],
    }
    (tmp_path / "Ep1_scene1_production_package.json").write_text(json.dumps(package), encoding="utf-8")

    with pytest.raises(ValueError, match="trim would cut line-1"):
        rough.save_scene_cut("Ep1", "1", [{
            "shotId": "S1.SH1", "inSec": 3, "outSec": 10, "manualTrim": True,
        }])


def test_scene_cut_opens_with_partial_approvals_but_cannot_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(rough, "OUT", tmp_path)
    first = tmp_path / "first.mp4"
    first.write_bytes(b"first")
    package = {
        "episode": "Ep1", "sceneNumber": 1,
        "shots": [
            {"shotId": "S1.SH1", "durationSec": 12},
            {"shotId": "S1.SH2", "durationSec": 10},
        ],
        "continuityLedger": [
            {"shotId": "S1.SH1", "status": "approved", "approvedTake": str(first)},
            {"shotId": "S1.SH2", "status": "ready"},
        ],
    }
    (tmp_path / "Ep1_scene1_production_package.json").write_text(json.dumps(package), encoding="utf-8")

    state = rough.scene_status("Ep1", "1")
    assert state["approvedCount"] == 1
    assert state["expectedCount"] == 2
    assert state["missingShotIds"] == ["S1.SH2"]
    assert state["allShotsApproved"] is False
    assert [entry["shotId"] for entry in state["sequence"]] == ["S1.SH1"]

    with pytest.raises(ValueError, match="finish WATCH approval.*S1.SH2"):
        rough.save_scene_cut("Ep1", "1", state["sequence"], confirm=True)
