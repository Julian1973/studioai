import pytest

import cb_render as render


def test_post_candidate_uses_current_unconfirmed_cut_without_approving_it(monkeypatch):
    package = {"shots": [{"shotId": "S1.SH1"}], "continuityLedger": [
        {"shotId": "S1.SH1", "status": "approved", "approvedTake": "/approved.mp4"}]}
    cut = {"confirmed": False, "confirmedCurrent": False, "sequence": [
        {"shotId": "S1.SH1", "inSec": 0, "outSec": 3, "manualTrim": False}]}
    monkeypatch.setattr(render.cb_rough_cut, "scene_edit_decision", lambda *a, **k: cut)
    sources, missing = render._scene_post_sources(package, "1", "EpTest")
    assert not missing
    assert sources[0]["approvedTake"] == "/approved.mp4"
    assert sources[0]["editOutSec"] == 3
    assert cut["confirmed"] is False
    assert cut["confirmedCurrent"] is False


def test_post_candidate_still_refuses_stale_cut(monkeypatch):
    package = {"shots": [{"shotId": "S1.SH1"}], "continuityLedger": [
        {"shotId": "S1.SH1", "status": "approved", "approvedTake": "/approved.mp4"}]}
    def stale(*args, **kwargs):
        raise ValueError("scene cut references changed or unavailable approved media")
    monkeypatch.setattr(render.cb_rough_cut, "scene_edit_decision", stale)
    with pytest.raises(ValueError, match="changed or unavailable"):
        render._scene_post_sources(package, "1", "EpTest")


def test_post_candidate_still_reports_unapproved_shots():
    package = {"shots": [{"shotId": "S1.SH1"}], "continuityLedger": [
        {"shotId": "S1.SH1", "status": "candidate", "approvedTake": "/candidate.mp4"}]}
    sources, missing = render._scene_post_sources(package, "1", "EpTest")
    assert sources == []
    assert missing == ["S1.SH1"]
