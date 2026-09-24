import hashlib
import json

import pytest

import cb_render
import studio_source_segmentation


def test_voice_word_lock_accepts_smart_apostrophes_and_acting_tags():
    assert cb_render.cb_voice_director.same_spoken_words(
        "[shocked] Oof! I can't see!", "Oof, I can’t see!")
    assert not cb_render.cb_voice_director.same_spoken_words(
        "Oof! I can't see!", "[shocked] Oof! Wow, I can’t see! Help me!")


def test_voice_working_save_routes_new_words_through_script_correction(
        monkeypatch, tmp_path):
    shot = {"shotId": "S4.SH3", "dialogueLines": [{
        "dialogueOccurrenceId": "occ-1", "sourceEventId": "event-1",
        "speaker": "Fuzzby", "exactText": "Oof! I can’t see!",
    }]}
    package = {"shots": [shot], "continuityLedger": [{"shotId": "S4.SH3"}]}
    monkeypatch.setattr(cb_render, "load_pkg", lambda *_: (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_save", lambda *_: None)
    save = cb_render.save_voice_working.__wrapped__

    accepted = save(4, "S4.SH3", [{
        "speaker": "Fuzzby", "text": "[shocked] Oof, I can't see!",
    }], episode="Ep4", log=lambda *_: None)
    assert accepted["lines"][0]["text"] == "[shocked] Oof, I can't see!"

    with pytest.raises(cb_render.Refused, match="Save corrected words"):
        save(4, "S4.SH3", [{
            "speaker": "Fuzzby", "text": "[shocked] Oof! Wow, I can't see! Help me!",
        }], episode="Ep4", log=lambda *_: None)


def test_hear_disables_fire_when_working_text_changes_script_words(monkeypatch, tmp_path):
    occurrence = "dialogue-occurrence:test"
    package = {
        "shots": [{"shotId": "S4.SH3", "dialogueLines": [{
            "dialogueOccurrenceId": occurrence, "speaker": "Fuzzby",
            "exactText": "Oof! I can't see!",
        }]}],
        "continuityLedger": [{"shotId": "S4.SH3", "workingVoice": {"lines": [{
            "dialogueOccurrenceId": occurrence, "speaker": "Fuzzby",
            "text": "[shocked] Oof! Wow, I can't see! Help me!",
        }]}}],
    }
    monkeypatch.setattr(cb_render, "load_pkg", lambda *_: (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_approved_department_output", lambda *args: {"lines": []})
    monkeypatch.setattr(cb_render, "_voice_source_validation",
                        lambda *_: {"ready": True, "message": None})

    status = cb_render.voice_performance_status("4", "S4.SH3", "Ep4")

    assert status["sourceValidation"]["ready"] is False
    assert "Save corrected words" in status["sourceValidation"]["message"]


def test_direct_preview_and_fire_share_fallback_without_current_voice_department(
        monkeypatch, tmp_path):
    line = {'dialogueOccurrenceId': 'occ-1', 'sourceEventId': 'event-1',
            'speaker': 'Sunny', 'exactText': 'A little sprinkle is good luck, right?',
            'delivery': '[nervous] A little sprinkle is good luck, right?'}
    shot = {'shotId': 'S3.SH1', 'dialogueLines': [line],
            'voiceDirectorBrief': [{'dialogueOccurrenceId': 'occ-1',
                                    'elevenLabsV3Direction': line['delivery']}]}
    package = {'shots': [shot], 'continuityLedger': [{'shotId': 'S3.SH1'}]}
    monkeypatch.setattr(cb_render, 'load_pkg', lambda *a: (package, tmp_path/'pkg.json'))
    def missing_direction(*_args):
        raise cb_render.Refused(
            'REFUSED — Prepare current Voice specialist direction for S3.SH1 first.')
    monkeypatch.setattr(cb_render, '_approved_department_output', missing_direction)
    status = cb_render.voice_performance_status('3', 'S3.SH1', 'Ep4')
    fire_lines, fire_source = cb_render._resolve_voice_lines(package, shot)
    assert status['approvedLines'][0]['exactText'] == line['exactText']
    assert status['approvedLines'][0]['scriptExactText'] == line['exactText']
    assert status['currentLines'][0]['text'] == '[nervous] '+line['exactText']
    assert status['source'] == fire_source == 'direct-current'
    assert status['currentLines'][0]['text'] == fire_lines[0]['text']
    assert not status['hasTake']
    assert status['sourceValidation']['ready'] is False


def test_voice_source_validation_requires_verified_spoken_boundaries():
    raw = "Oof! I can’t see! He waddles around angrily."
    spoken = "Oof! I can’t see!"
    script = spoken + "\n" + "He waddles around angrily."
    line = {"dialogueOccurrenceId": "occ-current", "speaker": "Fuzzby",
            "exactText": raw}
    blocked = cb_render._voice_source_validation({"dialogueLines": [line]})
    assert blocked["ready"] is False
    assert "silent script action" in blocked["message"]

    line["sourceSegmentation"] = studio_source_segmentation.project(
        line, script, boundary={
            "scriptRevision": "sha256:" + hashlib.sha256(script.encode()).hexdigest(),
            "occurrenceId": "occ-current", "speaker": "Fuzzby",
            "authority": "reviewed_source_boundaries", "evidenceId": "review-1",
            "spans": {"spokenText": [0, len(spoken)],
                      "actionAfter": [len(spoken) + 1, len(script)]},
        })
    assert cb_render._voice_source_validation({"dialogueLines": [line]}) == {
        "ready": True, "message": None}


def test_scoped_voice_rebase_updates_every_line_and_source_projection():
    first_raw = "Oof! I can’t see! He waddles around angrily."
    first_spoken = "Oof! I can’t see!"
    second = "I have been HONEYED!"
    script = f"FUZZBY\n{first_spoken}\n\n{second}\n"
    events = [
        {"i": 1, "speaker": "Fuzzby", "text": first_spoken,
         "dialogueOccurrenceId": "occ-current-1", "sourceEventId": "event-current-1"},
        {"i": 2, "speaker": "Fuzzby", "text": second,
         "dialogueOccurrenceId": "occ-current-2", "sourceEventId": "event-current-2"},
    ]
    shot = {
        "shotId": "S4.SH3",
        "dialogueLines": [
            {"dialogueOccurrenceId": "occ-old-1", "sourceEventId": "event-old-1",
             "speaker": "Fuzzby", "exactText": first_raw},
            {"dialogueOccurrenceId": "occ-old-2", "sourceEventId": "event-old-2",
             "speaker": "Fuzzby", "exactText": second},
        ],
        "voiceDirectorBrief": [
            {"dialogueOccurrenceId": "occ-old-1", "elevenLabsV3Direction": first_raw},
            {"dialogueOccurrenceId": "occ-old-2", "elevenLabsV3Direction": second},
        ],
    }

    _, old_texts = cb_render._rebase_shot_dialogue_sources(
        shot, events, script, 0, first_spoken)

    assert old_texts == [first_raw, second]
    assert [line["dialogueOccurrenceId"] for line in shot["dialogueLines"]] == [
        "occ-current-1", "occ-current-2"]
    assert [line["sourceEventId"] for line in shot["dialogueLines"]] == [
        "event-current-1", "event-current-2"]
    assert [studio_source_segmentation.spoken(line)
            for line in shot["dialogueLines"]] == [first_spoken, second]
    assert [brief["dialogueOccurrenceId"] for brief in shot["voiceDirectorBrief"]] == [
        "occ-current-1", "occ-current-2"]
    assert shot["voiceDirectorBrief"][0]["elevenLabsV3Direction"] == first_spoken


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


def test_voice_status_previews_saved_prompt_and_marks_old_take_stale(monkeypatch, tmp_path):
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

    assert status["source"] == "human-working"
    assert status["currentLines"][0]["text"] == "[questioning] Nailed it."
    assert status["takeMatchesCurrent"] is False
    assert status["isWorking"] is True
    assert status["takeKind"] == "complete-shot-track"
    assert status["generatedLineCount"] == 1
    assert status["expectedLineCount"] == 1
    assert status["shotDurationSec"] == 9


def test_voice_status_marks_working_prompt_when_it_is_current(monkeypatch, tmp_path):
    occurrence = "dialogue-occurrence:test"
    text = "[curious] Just a drop?"
    package = {
        "shots": [{"shotId": "S4.SH2", "dialogueLines": [{
            "dialogueOccurrenceId": occurrence, "speaker": "Keen",
            "exactText": "Just a drop?"}]}],
        "continuityLedger": [{"shotId": "S4.SH2", "workingVoice": {
            "savedAt": "2026-09-23T22:51:17", "lines": [{
                "dialogueOccurrenceId": occurrence, "speaker": "Keen", "text": text}]}}],
    }
    monkeypatch.setattr(cb_render, "load_pkg", lambda *a: (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_approved_department_output", lambda *a: {"lines": []})
    monkeypatch.setattr(cb_render, "_approved_voice_lines", lambda *a: [{
        "dialogueOccurrenceId": occurrence, "speaker": "Keen", "text": text}])

    status = cb_render.voice_performance_status("4", "S4.SH2", "Ep4")

    assert status["currentLines"][0]["text"] == text
    assert status["isWorking"] is True
    assert status["hasTake"] is False


def test_voice_status_exposes_local_tempo_recovery(monkeypatch, tmp_path):
    take = tmp_path / "take.wav"
    take.write_bytes(b"audio")
    placement = tmp_path / "take.wav.timing.json"
    placement.write_text(json.dumps({
        "tempoAdjusted": True,
        "tempoFactor": 1.093,
        "performanceTargetStartSec": 1.2,
        "performanceTargetEndSec": 29.9,
        "providerCalledForTimingRecovery": False,
        "placements": [],
    }))
    package = {
        "shots": [{"shotId": "S4.SH1", "durationSec": 30, "dialogueLines": []}],
        "continuityLedger": [{
            "shotId": "S4.SH1", "voPath": str(take),
            "voPlacementPath": str(placement),
        }],
    }
    monkeypatch.setattr(
        cb_render, "load_pkg", lambda scene, episode="Ep1": (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_approved_department_output", lambda *args: {"lines": []})
    monkeypatch.setattr(cb_render, "_approved_voice_lines", lambda *args: [])

    status = cb_render.voice_performance_status("4", "S4.SH1", "Ep2")

    assert status["timingRecovery"] == {
        "tempoAdjusted": True,
        "tempoFactor": 1.093,
        "performanceTargetStartSec": 1.2,
        "performanceTargetEndSec": 29.9,
        "providerCalled": False,
    }


def test_take_remains_current_when_only_compiler_audit_hash_changes(
        tmp_path, monkeypatch):
    take = tmp_path / "voice.wav"
    take.write_bytes(b"voice")
    generated = [{
        "dialogueOccurrenceId": "occ-1", "sourceEventId": "event-1",
        "speaker": "Fuzzby", "text": "[casual] Nailed it.",
        "compiledHash": "old-audit-hash",
    }]
    package = {
        "sceneNumber": "1", "episode": "Ep1",
        "shots": [{
            "shotId": "S1.SH1", "durationSec": 9,
            "dialogueLines": [{
                "dialogueOccurrenceId": "occ-1", "sourceEventId": "event-1",
                "speaker": "Fuzzby", "exactText": "Nailed it.",
                "delivery": "[casual] Nailed it.",
            }],
        }],
        "continuityLedger": [{
            "shotId": "S1.SH1", "voPath": str(take),
            "voGeneratedFrom": generated,
        }],
    }
    monkeypatch.setattr(
        cb_render, "load_pkg", lambda scene, episode="Ep1": (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_approved_department_output", lambda *args: {"lines": []})
    status = cb_render.voice_performance_status("1", "S1.SH1", "Ep1")

    assert status["source"] == "direct-current"
    assert status["takeMatchesCurrent"] is True
