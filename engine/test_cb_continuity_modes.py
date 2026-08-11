import pytest

import cb_costs
import cb_render as R


def test_video_extension_plan_uses_previous_approved_clip_as_video_reference(tmp_path, monkeypatch):
    previous = tmp_path / "previous.mp4"
    anchor = tmp_path / "anchor.png"
    previous.write_bytes(b"previous clip")
    anchor.write_bytes(b"anchor")
    pkg = {
        "episode": "EpT",
        "sceneNumber": "1",
        "shots": [
            {"shotId": "S1", "sourceType": "opener"},
            {"shotId": "S2", "sourceType": "relay", "sourceShotId": "S1",
             "durationSec": 6, "seedancePrompt": "Shot 1: Continue. End state: settled.",
             "referenceSlots": {}, "dialogueLines": []},
        ],
        "continuityLedger": [
            {"shotId": "S1", "status": "approved", "approvedTake": str(previous),
             "harvestFrame": str(anchor)},
            {"shotId": "S2", "status": "designed",
             "continuityMode": R.CONTINUITY_MODE_VIDEO_EXTENSION},
        ],
    }
    monkeypatch.setattr(R, "_reference_records", lambda shot, imgs: [])
    monkeypatch.setattr(R, "_review_video_resolution", lambda: "480p")
    monkeypatch.setattr(R.cb_providers, "request_contract", lambda **kwargs: {
        "providerModelId": "fal-seedance-2.5",
        "modelVersion": "2.5",
        "transport": "fal-subscribe",
        "resolution": kwargs["resolution"],
        "costRateKey": "seedance_25_fal_480p_per_sec",
    })
    monkeypatch.setattr(cb_costs, "estimate_video_cost", lambda *a, **k: 0.1)

    plan = R._animation_execution_plan(
        pkg, pkg["shots"][1], pkg["continuityLedger"][1], [], str(anchor), False)

    segment = plan["segments"][0]
    assert plan["continuityMode"] == R.CONTINUITY_MODE_VIDEO_EXTENSION
    assert segment["videoReferences"][0]["slot"] == "@Video1"
    assert segment["videoReferences"][0]["path"] == str(previous)
    assert segment["contract"]["resolution"] == "480p"
    assert "Continue forward naturally from @Video1" in segment["prompt"]


def test_video_extension_mode_refuses_on_opening_shot(tmp_path, monkeypatch):
    pkg = {
        "episode": "EpT", "sceneNumber": "1",
        "shots": [{"shotId": "S1", "sourceType": "opener"}],
        "continuityLedger": [{"shotId": "S1", "status": "designed"}],
    }
    monkeypatch.setattr(R, "load_pkg", lambda scene, episode: (pkg, tmp_path / "pkg.json"))
    monkeypatch.setattr(R, "_save", lambda *args, **kwargs: None)
    with pytest.raises(R.Refused, match="opening shots"):
        R.set_continuity_mode("1", "S1", R.CONTINUITY_MODE_VIDEO_EXTENSION, "EpT")
