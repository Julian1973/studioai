import cb_render


def test_reject_voice_clears_recoverable_failed_take(monkeypatch, tmp_path):
    voice = tmp_path / "rejected.wav"
    voice.write_bytes(b"rejected performance")
    ledger = {
        "shotId": "S6.SH2",
        "voPath": str(voice),
        "voiceApproval": {"approved": True},
        "voGeneratedFrom": [{"text": "old performance"}],
        "voicePlacementFailure": {
            "rawPath": str(tmp_path / "old-raw.mp3"),
            "timingPath": str(tmp_path / "old-timing.json"),
            "generatedFrom": [{"text": "old performance"}],
        },
    }
    package = {"continuityLedger": [ledger]}

    monkeypatch.setattr(cb_render, "HERE", tmp_path)
    monkeypatch.setattr(cb_render, "load_pkg", lambda scene, episode: (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_save", lambda package, path: None)

    cb_render.reject_voice(6, "S6.SH2", "Performance rejected", episode="Ep2")

    assert ledger["voPath"] is None
    assert ledger["voiceApproval"] is None
    assert ledger["voicePlacementFailure"] is None
