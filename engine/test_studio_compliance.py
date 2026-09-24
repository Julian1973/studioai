"""Compliance catches measured cross-stage timing drift before WATCH."""
import copy

import cb_render
import studio_approved_media_projection
import cb_production_preflight as compliance


def test_measured_hear_conflict_is_routed_back_to_direct(monkeypatch):
    shot = {
        "shotId": "S4.SH1",
        "dialogueLines": [{"speaker": "Sunny", "exactText": "Just watch!",
                           "startSec": 23.35, "endSec": 29.5}],
        "directorCard": {"stateChanges": [{"entityId": "char:Sunny", "atSec": 20.5,
            "cause": "After Sunny finishes 'Just watch!', she turns to the wall."}]},
    }
    ledger = {"voiceApproval": {"approved": True}, "voPlacementPath": "verified-receipt"}
    package = {"shots": [shot]}
    monkeypatch.setattr(cb_render, "_ledger", lambda _pkg, _sid: ledger)
    def project(source, _ledger):
        measured = copy.deepcopy(source)
        measured["dialogueLines"][0]["endSec"] = 29.5
        return measured
    monkeypatch.setattr(studio_approved_media_projection, "watch_shot", project)

    findings = compliance._causal_timing_compliance(package)

    assert len(findings) == 1
    assert findings[0]["code"] == "DIRECT_AUDIO_TIMING_CONFLICT"
    assert findings[0]["stage"] == "storyboard"
    assert findings[0]["shotId"] == "S4.SH1"
    assert "ends at 29.5s" in findings[0]["message"]
    assert "Revise the conflicting DIRECT checkpoint" in findings[0]["action"]


def test_compliance_ignores_unapproved_voice(monkeypatch):
    monkeypatch.setattr(cb_render, "_ledger", lambda *_: {"voiceApproval": {"approved": False}})
    monkeypatch.setattr(studio_approved_media_projection, "watch_shot",
                        lambda *_: (_ for _ in ()).throw(AssertionError("must not project")))
    assert compliance._causal_timing_compliance({"shots": [{"shotId": "S4.SH1"}]}) == []
