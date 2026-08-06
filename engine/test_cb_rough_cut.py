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
    (root / "Ep1_scene1_production_package.json").write_text(json.dumps(package))


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
