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
        "continuityLedger": [{
            "shotId": "S1.SH1",
            "voiceApproval": {"approved": True, "reviewedBy": "Julian"},
        }],
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
    assert status["voiceApprovalRecorded"] is True


def test_voice_status_uses_compiled_track_instead_of_stale_working_prompt(monkeypatch, tmp_path):
    occurrence = "dialogue-occurrence:test"
    take = tmp_path / "take.wav"
    take.write_bytes(b"audio")
    placement = tmp_path / "take.wav.timing.json"
    placement.write_text('{"placements":[{"dialogueIndex":0}]}')
    compiled = [{
        "dialogueOccurrenceId": occurrence,
        "sourceEventId": "script-event:test",
        "speaker": "Fuzzby",
        "text": "[casual] Nailed it.",
        "voiceId": "voice",
        "modelId": "eleven_v3",
        "voiceSettings": {},
        "previousText": "runway",
        "compiledHash": "hash",
        "recipeId": "C",
    }]
    package = {
        "shots": [{"shotId": "S1.SH1", "durationSec": 9, "dialogueLines": [{
            "dialogueOccurrenceId": occurrence, "sourceEventId": "script-event:test",
            "speaker": "Fuzzby", "exactText": "Nailed it.",
        }]}],
        "continuityLedger": [{
            "shotId": "S1.SH1",
            "workingVoice": {"savedAt": "2026-08-08T19:51:02", "lines": [{
                "dialogueOccurrenceId": occurrence, "sourceEventId": "script-event:test",
                "speaker": "Fuzzby", "text": "[questioning] Nailed it.",
            }]},
            "voPath": str(take), "voGeneratedFrom": compiled,
            "voPlacementPath": str(placement),
        }],
    }
    monkeypatch.setattr(
        cb_render, "load_pkg", lambda scene, episode="Ep1": (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_approved_department_output", lambda *args: {"lines": []})
    monkeypatch.setattr(cb_render, "_approved_voice_lines", lambda pkg, shot: compiled)

    status = cb_render.voice_performance_status("1", "S1.SH1", "Ep1")

    assert status["source"] == "voice-director-compiled"
    assert status["currentLines"][0]["text"] == "[casual] Nailed it."
    assert status["takeMatchesCurrent"] is True
    assert status["isWorking"] is False
    assert status["takeKind"] == "complete-shot-track"
    assert status["generatedLineCount"] == 1
    assert status["expectedLineCount"] == 1
    assert status["shotDurationSec"] == 9
