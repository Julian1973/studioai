import hashlib

import cb_render
from cb_audio_authority import route_line


def _script():
    return (
        "INT. PARTY CAVE - DAY 4\n\n"
        "SUNNY\nGrab your partner, do-si-do! Round and round the honey goes!\n\n"
        "SUNNY\nWhoa, whoa, whoaaaa! They slide across the cave floor and SMASH into a pile of cushions. BUZZ-CRASH.\n\n"
        "SUNNY\nTa-da! Everyone is having fun… Right?\n\n"
        "FUZZBY\nI’m too sticky for this!\n"
    )


def _shot():
    texts = [
        "Grab your partner, do-si-do! Round and round the honey goes!",
        "Whoa, whoa, whoaaaa! They slide across the cave floor and SMASH into a pile of cushions. BUZZ-CRASH.",
        "Ta-da! Everyone is having fun… Right?",
        "I’m too sticky for this!",
    ]
    speakers = ["Sunny", "Sunny", "Sunny", "Fuzzby"]
    return {
        "shotId": "S4.SH4",
        "dialogueLines": [
            {"dialogueOccurrenceId": f"occ-{index}", "speaker": speaker,
             "exactText": text}
            for index, (speaker, text) in enumerate(zip(speakers, texts), 1)
        ],
    }


def _runtime(monkeypatch, tmp_path, *, vo_path=None):
    script = _script()
    script_path = tmp_path / "current-script.txt"
    script_path.write_text(script, encoding="utf-8")
    revision = "sha256:" + hashlib.sha256(script.encode("utf-8")).hexdigest()
    shot = _shot()
    pkg = {"shots": [shot], "continuityLedger": [
        {"shotId": "S4.SH4", "voPath": vo_path}],
    }
    saved = []
    monkeypatch.setattr(cb_render, "load_pkg", lambda *_: (pkg, script_path))
    monkeypatch.setattr(cb_render, "_require_valid", lambda *_: None)
    monkeypatch.setattr(cb_render, "_require_current_lineage", lambda *_: None)
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: {})
    monkeypatch.setattr(cb_render, "_resolve_char", lambda name, _cfg: str(name).casefold())
    monkeypatch.setattr(cb_render, "_save", lambda package, path: saved.append((package, path)))
    monkeypatch.setattr(cb_render, "SCRIPT_STORE", type("Store", (), {
        "current": lambda *_args, **_kwargs: {"scriptVersionId": revision},
        "content_path": lambda *_args, **_kwargs: script_path,
    })())
    return pkg, shot, saved, script


def test_reviewed_hear_boundary_keeps_script_action_out_of_spoken_line(
        monkeypatch, tmp_path):
    pkg, shot, saved, script = _runtime(monkeypatch, tmp_path)
    second = shot["dialogueLines"][1]
    raw = second["exactText"]
    shot["voiceDirectorBrief"] = [{
        "dialogueOccurrenceId": second["dialogueOccurrenceId"],
        "exactDialogue": raw,
        "elevenLabsV3Direction": raw,
        "dramaticIntention": "Keep the loss of control comic until impact.",
    }]
    speech = "Whoa, whoa, whoaaaa!"
    action = "They slide across the cave floor and SMASH into a pile of cushions. BUZZ-CRASH."
    result = cb_render.review_voice_source_boundaries.__wrapped__(
        4, "S4.SH4", {second["dialogueOccurrenceId"]: {
            "spokenText": speech, "actionAfter": action,
            "reason": "The impact is screenplay action and SFX, not Sunny's spoken line.",
        }}, episode="Ep4", reviewed_by="Codex at producer request", log=lambda *_: None)

    assert result["spokenLines"][1] == speech
    assert result["actionAfter"][1] == action
    assert result["briefsCleaned"] == 1
    assert result["audioGenerated"] is False
    assert result["providerCalled"] is False
    assert len(saved) == 1
    assert second["exactText"] == raw  # source stays immutable
    assert second["sourceSegmentation"]["scriptRevision"] == "sha256:" + hashlib.sha256(
        script.encode("utf-8")).hexdigest()
    brief = shot["voiceDirectorBrief"][0]
    assert brief["exactDialogue"] == speech
    assert brief["elevenLabsV3Direction"] == speech
    assert brief["dramaticIntention"] == "Keep the loss of control comic until impact."
    routed, cue = route_line(second)
    assert routed["exactText"] == speech
    assert routed["scriptExactText"] == raw
    assert cue is None
    assert cb_render._voice_source_validation(shot)["ready"] is True
    assert all(line.get("sourceSegmentation") for line in pkg["shots"][0]["dialogueLines"])


def test_reviewed_hear_boundary_refuses_to_touch_existing_voice_work(monkeypatch, tmp_path):
    _pkg, shot, saved, _script_text = _runtime(monkeypatch, tmp_path, vo_path="accepted.wav")
    second = shot["dialogueLines"][1]
    try:
        cb_render.review_voice_source_boundaries.__wrapped__(
            4, "S4.SH4", {second["dialogueOccurrenceId"]: {
                "spokenText": "Whoa, whoa, whoaaaa!",
                "actionAfter": "They slide across the cave floor and SMASH into a pile of cushions. BUZZ-CRASH.",
                "reason": "Action is not speech.",
            }}, episode="Ep4", reviewed_by="Codex at producer request", log=lambda *_: None)
    except cb_render.Refused as exc:
        assert "already has voice work" in str(exc)
    else:
        raise AssertionError("existing voice work must be protected")
    assert not saved
    assert all(line.get("sourceSegmentation") is None for line in shot["dialogueLines"])


def test_hear_acting_helper_hides_script_prose_and_keeps_only_relevant_v3_tags():
    prose = (
        "ElevenLabs text for Sunny’s spoken words: [nervous] It’s fine! "
        "It’s okay! Everything is fine! Do not vocalize the action after this line."
    )
    assert cb_render._safe_voice_delivery_note(
        prose, "It’s fine! It’s okay! Everything is fine!") == "[nervous]"
    assert cb_render._safe_voice_delivery_note(
        "Whoa! They slide across the floor.", "Whoa!") is None
    assert cb_render._safe_voice_delivery_note(
        "[excited] Party time!", "Party time!") == "[excited]"
