import cb_dailies


def _snapshot(**extra):
    value = {
        "episode": "Ep2", "scene": "3", "beat": "Bo hesitates",
        "shotId": "3.B1.S1", "candidateId": "C1", "assetPath": "/tmp/take.mp4",
        "assetHash": "asset-1", "promptHash": "prompt-1", "audioVersion": "audio-1",
        "storyBeat": "Bo decides whether to leave", "openingFrame": "frame-a",
        "landingFrame": "frame-b", "audioAsset": "voice.wav", "timing": {"durationSec": 30},
    }
    value.update(extra)
    return value


def test_dailies_requires_only_rating_decision_and_note(tmp_path, monkeypatch):
    monkeypatch.setattr(cb_dailies, "PATH", tmp_path / "dailies.jsonl")
    review = cb_dailies.record(_snapshot(), rating=3, decision="retake", note="voice clips", cost=1.2)
    assert review["analysis"]["likelyFailedLayer"]["category"] == "audio/lip-sync"
    assert review["diagnosisState"] == "awaiting-confirmation"
    assert cb_dailies.report()["count"] == 1


def test_retake_is_compared_without_auto_firing(tmp_path, monkeypatch):
    monkeypatch.setattr(cb_dailies, "PATH", tmp_path / "dailies.jsonl")
    first = cb_dailies.record(_snapshot(), rating=2, decision="retake", note="emotion is flat")
    second = cb_dailies.record(_snapshot(assetHash="asset-2", promptHash="prompt-2"),
                               rating=4, decision="approve", retake_of=first["recordId"])
    comparison = cb_dailies.compare(second["recordId"])
    assert comparison["ratingImproved"] is True
    assert comparison["ratingDelta"] == 2
    assert comparison["changed"]["prompt"] is True
    assert second["decision"] == "approve"
