import json

import cb_render as R


def _original(name):
    if name == "reject_shot":
        return getattr(R.reject_shot, "__wrapped__", R.reject_shot)
    for wrapped in (R.approve_shot, R.reject_shot):
        for cell in (getattr(wrapped, "__wrapped__", wrapped).__closure__ or []):
            value = cell.cell_contents
            if isinstance(value, dict) and name in value:
                return value[name]
    raise AssertionError(f"original {name} not found")


def _pending_pkg(tmp_path):
    candidate = tmp_path / "candidate.mp4"
    candidate.write_bytes(b"candidate")
    pkg = {
        "episode": "EpT",
        "sceneNumber": "1",
        "validation": {"passed": True},
        "shots": [{"shotId": "S1", "durationSec": 6, "seedancePrompt": "Shot 1: Action. End state: done."}],
        "continuityLedger": [{
            "shotId": "S1",
            "status": "candidates-pending",
            "candidatePaths": [str(candidate)],
            "batchId": "batch-1",
            "batch": {
                "batchId": "batch-1",
                "envelope": {"prompt": "Shot 1: Action. End state: done."},
                "envelopeHash": "",
            },
        }],
    }
    env = pkg["continuityLedger"][0]["batch"]["envelope"]
    pkg["continuityLedger"][0]["batch"]["envelopeHash"] = R.hashlib.sha256(
        json.dumps(env, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return pkg, candidate


def test_approve_banks_prompt_automatically(tmp_path, monkeypatch):
    pkg, candidate = _pending_pkg(tmp_path)
    calls = []
    monkeypatch.setattr(R, "load_pkg", lambda scene, episode: (pkg, tmp_path / "pkg.json"))
    monkeypatch.setattr(R, "_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(R, "_require_current_lineage", lambda *args, **kwargs: None)
    monkeypatch.setattr(R.cb_gen, "last_frame", lambda selected, out: tmp_path.joinpath("final.png").write_bytes(b"png"))
    monkeypatch.setattr(R, "_bank_animation_prompt", lambda *args, **kwargs: calls.append(kwargs) or {
        "recordId": "bank-1", "outcome": kwargs["outcome"], "bankedAt": "now"})

    _original("approve_shot")(
        "1", "S1", 1, "EpT", log=lambda *args, **kwargs: None)

    assert calls and calls[0]["outcome"] == "approved"
    assert calls[0]["candidate"] == 1
    assert calls[0]["candidate_path"] == str(candidate)
    assert pkg["continuityLedger"][0]["promptBankRecords"][0]["recordId"] == "bank-1"


def test_reject_banks_prompt_with_diagnosis(tmp_path, monkeypatch):
    pkg, _ = _pending_pkg(tmp_path)
    calls = []
    monkeypatch.setattr(R, "load_pkg", lambda scene, episode: (pkg, tmp_path / "pkg.json"))
    monkeypatch.setattr(R, "_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(R, "_require_current_lineage", lambda *args, **kwargs: None)
    monkeypatch.setattr(R, "_bank_animation_prompt", lambda *args, **kwargs: calls.append(kwargs) or {
        "recordId": "bank-2", "outcome": kwargs["outcome"], "bankedAt": "now"})

    _original("reject_shot")(
        "1", "S1", "timing is too slow", "action-timing", "EpT",
        log=lambda *args, **kwargs: None)

    assert calls and calls[0]["outcome"] == "rejected"
    assert calls[0]["diagnosis"] == "timing is too slow"
    assert calls[0]["category"] == "action-timing"
    assert pkg["continuityLedger"][0]["promptBankRecords"][0]["recordId"] == "bank-2"
