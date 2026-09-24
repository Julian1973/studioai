from contextlib import nullcontext
from pathlib import Path

import pytest

import cb_outcome_chat as outcome


def _review_fixture(tmp_path):
    files = {}
    for name, content in (("audio.wav", b"reviewed-audio"),
                          ("raw.wav", b"raw-audio"),
                          ("timing.json", b"timing"),
                          ("placement.json", b"placement")):
        path = tmp_path / name
        path.write_bytes(content)
        files[name] = str(path)
    shot = {
        "shotId": "S4.SH3",
        "dialogueLines": [{
            "dialogueOccurrenceId": "line-1", "speaker": "Fuzzby",
            "exactText": "Oof! I can't see!", "startSec": 0.5, "endSec": 4.0,
        }],
    }
    ledger = {
        "shotId": shot["shotId"], "voPath": files["audio.wav"],
        "voRawPath": files["raw.wav"], "voTimingPath": files["timing.json"],
        "voPlacementPath": files["placement.json"],
        "voGeneratedFrom": [{"dialogueOccurrenceId": "line-1", "text": "old words"}],
        "voInputSignature": {"performanceHash": "old"},
        "workingVoice": {"lines": [{"dialogueOccurrenceId": "line-1", "text": "new words"}]},
    }
    pkg = {"episode": "Ep4", "sceneNumber": "4", "shots": [shot],
           "continuityLedger": [ledger]}
    return pkg, files


def _patch_outcome(monkeypatch, pkg, approve):
    monkeypatch.setattr(outcome.R, "load_pkg", lambda *_args, **_kwargs: (pkg, None))
    monkeypatch.setattr(outcome.cb_db, "scene_lease", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(outcome.R, "approve_voice", approve)


def test_override_intent_is_explicit_and_distinct_from_normal_approval():
    assert outcome.intent("approve voice as heard") == {"kind": "approve-voice-override"}
    assert outcome.intent("approve voice") == {"kind": "approve", "targetKind": "voice"}


def test_review_target_seals_audio_bundle_and_saved_voice_direction(tmp_path, monkeypatch):
    pkg, files = _review_fixture(tmp_path)
    _patch_outcome(monkeypatch, pkg, lambda *_args, **_kwargs: None)
    first = outcome.target("Ep4", "4", "S4.SH3", "voice")
    assert first["kind"] == "voice"

    pkg["continuityLedger"][0]["workingVoice"]["lines"][0]["text"] = "another saved line"
    second = outcome.target("Ep4", "4", "S4.SH3", "voice")
    assert second["hash"] != first["hash"]

    pkg["continuityLedger"][0]["workingVoice"]["lines"][0]["text"] = "new words"
    files_path = Path(files["placement.json"])
    files_path.write_bytes(b"changed timing receipt")
    third = outcome.target("Ep4", "4", "S4.SH3", "voice")
    assert third["hash"] != first["hash"]


def test_override_uses_the_exact_review_hash_and_calls_only_approval(tmp_path, monkeypatch):
    pkg, _ = _review_fixture(tmp_path)
    calls = []
    _patch_outcome(monkeypatch, pkg,
                   lambda *args, **kwargs: calls.append((args, kwargs)) or {"approved": True})
    reviewed = outcome.target("Ep4", "4", "S4.SH3", "voice")

    result = outcome.execute("Ep4", "4", "S4.SH3", "voice", reviewed["hash"],
                             "Producer", producer_override=True)

    assert result == {"approved": True}
    assert len(calls) == 1
    assert calls[0][1]["producer_override"] is True
    assert calls[0][1]["reviewed_by"] == "Producer"
    assert "approved it as heard" in calls[0][1]["override_reason"]


def test_override_refuses_if_the_reviewed_bundle_changes(tmp_path, monkeypatch):
    pkg, files = _review_fixture(tmp_path)
    calls = []
    _patch_outcome(monkeypatch, pkg,
                   lambda *args, **kwargs: calls.append((args, kwargs)))
    reviewed = outcome.target("Ep4", "4", "S4.SH3", "voice")
    Path(files["audio.wav"]).write_bytes(b"replacement-audio")

    with pytest.raises(outcome.R.Refused, match="reviewed item changed"):
        outcome.execute("Ep4", "4", "S4.SH3", "voice", reviewed["hash"],
                        "Producer", producer_override=True)
    assert not calls
