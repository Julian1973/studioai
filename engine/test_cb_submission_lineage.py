import pytest
import cb_render as render


def test_stale_handover_refuses_before_submission(monkeypatch):
    monkeypatch.setattr(render, "lineage_status", lambda *args: {
        "current": False, "reasonCodes": ["storyboard-content-mismatch"]})
    with pytest.raises(render.Refused, match="storyboard-content-mismatch"):
        render._require_current_lineage({}, "1", "EpT")


def test_current_scoped_handover_passes(monkeypatch):
    report = {"current": True, "reasonCodes": []}
    monkeypatch.setattr(render, "lineage_status", lambda *args: report)
    assert render._require_current_lineage({}, "1", "EpT") is report
