import pathlib

import cb_render


def test_uploaded_watch_render_becomes_zero_spend_pending_candidate(tmp_path, monkeypatch):
    source = tmp_path / "review.mp4"
    source.write_bytes(b"review-video")
    media = tmp_path / "shots"
    ledger = {
        "shotId": "S1.SH1",
        "status": "designed",
        "keyframeApproval": {"approved": True},
    }
    shot = {"shotId": "S1.SH1", "durationSec": 8, "dialogueLines": []}
    package = {
        "revision": 12,
        "creativeDirectingStandardVersion": 2,
        "shots": [shot],
        "continuityLedger": [ledger],
    }
    saved = []

    monkeypatch.setattr(cb_render, "MEDIA", media)
    monkeypatch.setattr(cb_render, "load_pkg", lambda scene, episode: (package, tmp_path / "package.json"))
    monkeypatch.setattr(cb_render, "_require_valid", lambda pkg: None)
    monkeypatch.setattr(cb_render, "_require_current_lineage", lambda pkg, scene, episode: None)
    monkeypatch.setattr(cb_render, "_require_stage_contract_keyframe", lambda current_shot, current_ledger: None)
    monkeypatch.setattr(cb_render.cb_post, "_dur", lambda path: 8.0)
    monkeypatch.setattr(cb_render, "_candidate_review", lambda *args, **kwargs: None)
    monkeypatch.setattr(cb_render, "_save", lambda pkg, path: saved.append((pkg, path)))

    record = cb_render.import_animation_candidate("1", "S1.SH1", source, "Ep2")

    candidate = pathlib.Path(ledger["candidatePaths"][0])
    assert candidate.is_file()
    assert candidate.read_bytes() == b"review-video"
    assert ledger["status"] == "candidates-pending"
    assert ledger["disclosure"] == {
        "packageRevision": 12,
        "source": "human-upload",
        "providerCalled": False,
        "estimatedCostUsd": 0,
    }
    assert record["costUsd"] == 0
    assert record["source"] == "human-upload"
    assert saved


def test_uploaded_watch_render_cannot_replace_pending_or_approved_work(tmp_path, monkeypatch):
    source = tmp_path / "review.mp4"
    source.write_bytes(b"review-video")
    shot = {"shotId": "S1.SH1", "durationSec": 8, "dialogueLines": []}
    ledger = {"shotId": "S1.SH1", "status": "candidates-pending"}
    package = {"revision": 12, "creativeDirectingStandardVersion": 2,
               "shots": [shot], "continuityLedger": [ledger]}
    monkeypatch.setattr(cb_render, "load_pkg", lambda scene, episode: (package, tmp_path / "package.json"))
    monkeypatch.setattr(cb_render, "_require_valid", lambda pkg: None)
    monkeypatch.setattr(cb_render, "_require_current_lineage", lambda pkg, scene, episode: None)

    try:
        cb_render.import_animation_candidate("1", "S1.SH1", source, "Ep2")
        assert False, "pending candidate should refuse replacement"
    except cb_render.Refused as exc:
        assert "already has a render awaiting review" in str(exc)

    ledger["status"] = "approved"
    try:
        cb_render.import_animation_candidate("1", "S1.SH1", source, "Ep2")
        assert False, "approved take should remain immutable"
    except cb_render.Refused as exc:
        assert "approved immutable take" in str(exc)
