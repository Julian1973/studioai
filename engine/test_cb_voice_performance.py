import cb_render


def test_voice_status_exposes_full_direction_beside_exact_provider_text(monkeypatch, tmp_path):
    occurrence = "dialogue-occurrence:test"
    package = {
        "shots": [{
            "shotId": "S1.SH1",
            "dialogueLines": [{
                "dialogueOccurrenceId": occurrence,
                "sourceEventId": "script-event:test",
                "speaker": "Fuzzby",
                "exactText": "Nailed it.",
                "delivery": "[proudly] Nailed it.",
            }],
        }],
        "continuityLedger": [{"shotId": "S1.SH1"}],
    }
    direction = {
        "lines": [{
            "dialogueOccurrenceId": occurrence,
            "sourceEventId": "script-event:test",
            "speaker": "Fuzzby",
            "performedText": "[proudly] Nailed it.",
            "dramaticIntention": "Cover the wobble with confidence.",
            "subtext": "That was intentional.",
            "cadenceAndBreath": "Compact, bright and slightly breathless.",
            "timingAndBody": "Land after the rebound while still trembling.",
        }],
    }
    monkeypatch.setattr(
        cb_render, "load_pkg", lambda scene, episode="Ep1": (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(
        cb_render, "_approved_department_output",
        lambda pkg, shot_id, stage: direction if stage == "voice" else {})

    status = cb_render.voice_performance_status("1", "S1.SH1", "Ep1")

    assert status["approvedLines"][0]["exactText"] == "Nailed it."
    assert status["currentLines"][0]["text"] == "[proudly] Nailed it."
    assert status["currentLines"][0]["dramaticIntention"] == (
        "Cover the wobble with confidence.")
    assert status["currentLines"][0]["cadenceAndBreath"] == (
        "Compact, bright and slightly breathless.")
    assert status["currentLines"][0]["timingAndBody"] == (
        "Land after the rebound while still trembling.")
