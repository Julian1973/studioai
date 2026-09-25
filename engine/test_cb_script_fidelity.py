"""T35 - the voice/dialogue contract, clause 2 and acceptance check 1.

Voice direction adds acting, never dialogue: the spoken words and the script's own
punctuation survive every voice path - the Voice Director's output, the producer's HEAR
prompt edit, the last check before a paid provider request, and intake itself.
"""
import copy

import pytest
import requests

import cb_gen
import cb_intake
import cb_render as render
import cb_voice_director as V
from test_cb_approval_policy import _pkg, isolated_canon  # noqa: F401 - autouse canon stub


# ── the one shared check ────────────────────────────────────────────────────────────

def test_tags_caps_and_pause_marks_are_acting_not_dialogue():
    exact = "It's fine! It's okay!"
    assert V.script_fidelity_problems("[nervous] It's FINE! [short pause] It's okay!", exact) == []
    assert V.script_fidelity_problems("It's fine!… It's, okay!", exact) == []
    assert V.script_fidelity_problems("It’s fine! It’s okay!", exact) == []   # curly == straight


def test_words_and_script_punctuation_are_locked():
    exact = "Uh-oh—"
    assert V.words_changed("Uh oh no—", exact)
    assert V.script_fidelity_problems("Uh-oh", exact)            # the interruption dash dropped
    assert V.script_fidelity_problems("Uh-oh!", exact)           # swapped for a non-pause mark
    assert V.script_fidelity_problems("[whispers] Uh-oh…—", exact) == []
    assert V.script_fidelity_problems(
        "Uh-oh—,", exact, allow_added_pauses=False)             # exactDialogue: nothing added


# ── the producer's HEAR prompt editor ───────────────────────────────────────────────

def _voice_pkg(tmp_path, monkeypatch, exact="I still feel him... every day."):
    package, shot, _ = _pkg(tmp_path)
    shot["dialogueLines"] = [{
        "dialogueOccurrenceId": "dialogue-1", "sourceEventId": "event-1",
        "speaker": "Fuzzby", "exactText": exact,
    }]
    saved = []
    monkeypatch.setattr(render, "load_pkg", lambda scene, episode="Ep1": (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(render, "_save", lambda pkg, path: saved.append(copy.deepcopy(pkg)))
    return package, shot, saved


def test_tag_only_prompt_edit_saves_and_leaves_the_script_alone(tmp_path, monkeypatch):
    package, shot, saved = _voice_pkg(tmp_path, monkeypatch)
    working = render.save_voice_working("1", shot["shotId"], [
        {"speaker": "Fuzzby", "text": "[quietly] I still feel him... [exhales] every day."}],
        log=lambda *_: None)
    assert working["lines"][0]["text"].startswith("[quietly]")
    assert "punctuationEdits" not in working["lines"][0]
    assert shot["dialogueLines"][0]["exactText"] == "I still feel him... every day."
    assert saved


def test_word_edit_in_the_prompt_becomes_an_unsaved_dialogue_draft(tmp_path, monkeypatch):
    package, shot, saved = _voice_pkg(tmp_path, monkeypatch)
    with pytest.raises(render.WordDraftRefused) as refused:
        render.save_voice_working("1", shot["shotId"], [
            {"speaker": "Fuzzby", "text": "[quietly] I still miss him... every day."}],
            log=lambda *_: None)
    draft = refused.value.draft[0]
    assert draft["dialogueOccurrenceId"] == "dialogue-1"
    assert draft["approvedText"] == "I still feel him... every day."
    assert draft["draftText"] == "I still miss him... every day."
    # nothing was saved and the approved script line is untouched
    assert not saved
    assert shot["dialogueLines"][0]["exactText"] == "I still feel him... every day."
    assert render._ledger(package, shot["shotId"]).get("workingVoice") is None


def test_producer_punctuation_glitch_fix_is_allowed_but_recorded(tmp_path, monkeypatch):
    _, shot, _ = _voice_pkg(tmp_path, monkeypatch)
    working = render.save_voice_working("1", shot["shotId"], [
        {"speaker": "Fuzzby", "text": "[quietly] I still feel him, every day."}],
        log=lambda *_: None)
    assert working["lines"][0]["punctuationEdits"]


def test_prompt_tags_must_come_from_the_speakers_registered_palette(tmp_path, monkeypatch):
    _, shot, _ = _voice_pkg(tmp_path, monkeypatch)
    with pytest.raises(render.Refused, match=r"outside Fuzzby's registered palette.*\[whatever\]"):
        render.save_voice_working("1", shot["shotId"], [
            {"speaker": "Fuzzby", "text": "[whatever] I still feel him... every day."}],
            log=lambda *_: None)


# ── the last check before a paid request ────────────────────────────────────────────

def test_stale_working_text_is_refused_before_the_provider(tmp_path, monkeypatch):
    package, shot, _ = _pkg(tmp_path)
    shot["dialogueLines"] = [{
        "dialogueOccurrenceId": "dialogue-1", "sourceEventId": "event-1",
        "speaker": "Fuzzby", "exactText": "I still feel him... every day.",
    }]
    ledger = render._ledger(package, shot["shotId"])
    # saved before a script correction: its words no longer match the approved line
    ledger["workingVoice"] = {"lines": [{
        "dialogueOccurrenceId": "dialogue-1", "sourceEventId": "event-1",
        "speaker": "Fuzzby", "text": "[quietly] I still miss him, every day.",
    }]}
    line = {
        "dialogueOccurrenceId": "dialogue-1", "sourceEventId": "event-1",
        "speaker": "Fuzzby", "character": "Fuzzby",
        "exactDialogue": "I still feel him... every day.",
        "performedText": "[quietly] I still feel him... every day.",
        "dramaticIntention": "Keep the thought connected.", "subtext": "Memory lives on.",
        "cadenceAndBreath": "Quiet.", "timingAndBody": "Still.",
        "archetypeId": "held-heart", "performanceQuestions": {
            "intention": "Connect.", "subtext": "Memory.", "thoughtBefore": "Plain.",
            "changeDuring": "Opens.", "operativeWords": ["every day"]},
        "physicalState": "Still.", "emotionalState": {"entry": "Held", "exit": "Open"},
        "listener": "Zenny", "bodyVoiceRelationship": "Still body.",
        "previousText": "A quiet look.", "startsAtSec": 1.0, "estimatedDurationSec": 2.0,
        "pauseReasons": ["The ellipsis holds the memory."],
        "tagPurposes": [{"tag": "quietly", "purpose": "Intimacy"}],
        "takeRecipes": [{"recipeId": "A", "label": "Primary",
                         "performedText": "[quietly] I still feel him... every day.",
                         "primary": True, "takesCount": 1}],
    }
    ledger.setdefault("departmentWork", {}).setdefault(
        "voice", {"approved": None, "candidate": None, "history": []})["candidate"] = {
        "output": {"shotId": shot["shotId"], "sceneIntention": "Memory.", "lines": [line]},
        "inputSignature": render._department_input_signature(
            package, "voice", shot["shotId"], "1", "Ep1"),
        "packageRevision": package["revision"],
    }
    with pytest.raises(render.Refused, match="no longer speaks the approved script words"):
        render._approved_voice_lines(package, shot)


def test_line_fallback_speaks_each_character_with_its_own_registered_settings(
        tmp_path, monkeypatch):
    sent = []

    class Resp:
        content = b"MP3"

    def fake_post(url, **kwargs):
        if "text-to-dialogue" in url:
            raise requests.HTTPError("dialogue endpoint refused")
        sent.append(kwargs["json"]["voice_settings"])
        return Resp()

    monkeypatch.setattr(cb_gen, "_rpost", fake_post)
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    monkeypatch.setattr(cb_gen, "ELEVEN_KEY", "sk_test_key")
    monkeypatch.setattr(cb_gen, "_ffprobe_duration", lambda path: 1.0)
    monkeypatch.setattr(cb_gen, "_concat_audio_parts",
                        lambda parts, out: out.write_bytes(b"MP3"))
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *a, **k: None)
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *a, **k: None)
    fuzzby = {"stability": 0.25, "similarity_boost": 0.7, "style": 0.4}
    zenny = {"stability": 0.55, "similarity_boost": 0.9, "style": 0.1}
    cb_gen.eleven_dialogue(
        [{"text": "Nice machine.", "voice_id": "fuzzby"},
         {"text": "OK, Fuzzby, calm down.", "voice_id": "zenny"}],
        out="fallback_vo.mp3", production_route="cb_render",
        voice_settings=[fuzzby, zenny])
    assert sent == [fuzzby, zenny]


# ── intake: screenplay directions never enter the spoken text ────────────────────────

def test_inline_parenthetical_is_lifted_out_of_the_spoken_words():
    script = "\n".join([
        "EXT. GREAT CLEARING - LATER  2",
        "",
        "Sunny straightens the berry cups.",
        "",
        "SUNNY",
        "It's fine! (beat) It's okay!",
        "",
    ])
    parsed = cb_intake.parse_script(script, log=lambda *_: None)
    dialogue = [e for e in parsed["events"] if e["type"] == "dialogue"]
    assert dialogue[0]["text"] == "It's fine! It's okay!"
    assert dialogue[0]["inlineDirections"] == ["beat"]
