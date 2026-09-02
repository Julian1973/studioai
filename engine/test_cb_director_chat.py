import json

import cb_director_chat as chat


def _package():
    return {
        "shots": [{
            "shotId": "S1.SH1",
            "purpose": "Bo decides whether to leave.",
            "openingPose": "Bo holds the conker at the satchel.",
            "dialogueLines": [{"speaker": "Bo", "exactText": "Today could be OK.",
                               "delivery": "trying to believe it"}],
        }],
        "continuityLedger": [{
            "shotId": "S1.SH1", "status": "designed",
            "keyframeScreening": {"reason": "Bo is staged too confidently."},
            "departmentWork": {},
        }],
    }


def test_director_chat_uses_small_context_and_persists(monkeypatch, tmp_path):
    monkeypatch.setattr(chat, "CHAT_DIR", tmp_path)
    monkeypatch.setattr(chat.cb_render, "load_pkg", lambda scene, episode: (_package(), tmp_path / "pkg.json"))
    captured = {}

    def fake_structured(system, user, schema, **kwargs):
        captured.update(system=system, user=json.loads(user), kwargs=kwargs)
        return chat.DirectorChatReply(
            response="Bo reads as confident. Keep the frame but make his choice physically uncertain.",
            correction="Stage Bo with the conker halfway into the satchel, shoulders raised and weight held back.",
            readyToApply=True,
        )

    monkeypatch.setattr(chat.cb_llm, "structured", fake_structured)
    result = chat.chat("Ep2", "1", "S1.SH1", "keyframe", "He is not anxious enough.")

    assert result["zeroMediaSpend"] is True
    assert result["reply"]["readyToApply"] is True
    assert captured["kwargs"]["model"] == chat.CHAT_MODEL
    assert captured["user"]["productionContext"]["exactDialogue"][0]["exactText"] == "Today could be OK."
    assert captured["user"]["productionContext"]["orderedShotStates"]["opening"] == "Bo holds the conker at the satchel."
    assert "accept ONE plain creative note" in captured["system"]
    assert "Never rewrite exact dialogue" in captured["system"]
    assert chat.history("Ep2", "1", "S1.SH1", "keyframe")["messages"][-1]["role"] == "director"


def test_director_chat_has_no_media_generation_or_approval_surface():
    source = open(chat.__file__, encoding="utf-8").read()
    assert "cb_gen" not in source
    assert "generate_image" not in source
    assert "generate_video" not in source
    assert "approve_" not in source
    assert "reject_" not in source


def test_director_agent_sees_spoken_and_seedance_sfx_as_separate_lanes(monkeypatch, tmp_path):
    package = _package()
    package["shots"][0]["dialogueLines"] = [
        {"speaker": "Fuzzby", "exactText": "ZZZZZ …", "startSec": 2, "endSec": 4}
    ]
    monkeypatch.setattr(chat.cb_render, "load_pkg", lambda scene, episode: (package, tmp_path / "pkg.json"))
    context = chat._scope_context("Ep2", "1", "S1.SH1", "voice", "Keep the snore out of ElevenLabs")
    assert context["exactDialogue"] == []
    assert context["seedanceSfxCues"][0]["kinds"] == ["snore"]
    assert "never enter @Audio1" in context["audioAuthority"]


def test_animation_edit_requires_explicit_valid_time_window():
    assert chat._requested_edit_window("change the smile", 24) is None
    assert chat._requested_edit_window("edit from 8.5s to 11s", 24) == (8.5, 11.0)
    assert chat._requested_edit_window("edit 23 to 28 seconds", 24) is None


def test_animation_edit_passes_local_review_frames_and_persists_range(monkeypatch, tmp_path):
    package = _package()
    package["shots"][0]["durationSec"] = 24
    package["continuityLedger"][0]["status"] = "approved"
    package["continuityLedger"][0]["approvedTake"] = "/protected/approved.mp4"
    monkeypatch.setattr(chat, "CHAT_DIR", tmp_path)
    monkeypatch.setattr(chat.cb_render, "load_pkg", lambda scene, episode: (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(chat, "_edit_review_frames", lambda path, start, end: ["start.jpg", "middle.jpg", "end.jpg"])
    captured = {}

    def fake_structured(system, user, schema, **kwargs):
        captured.update(system=system, user=json.loads(user), kwargs=kwargs)
        return chat.DirectorChatReply(
            response="I reviewed the section. Keep the entry and change only the reaction.",
            correction="From 8.5 to 11 seconds, Zenny opens one eye, smiles, then closes it.",
            protectedElements=["all motion before 8.5 seconds", "all motion after 11 seconds"],
            readyToApply=True, editStartSec=8.5, editEndSec=11,
        )

    monkeypatch.setattr(chat.cb_llm, "structured", fake_structured)
    result = chat.chat("Ep2", "1", "S1.SH1", "animation-edit", "Edit 8.5s to 11s: fix Zenny's reaction.")

    assert captured["kwargs"]["images"] == ["start.jpg", "middle.jpg", "end.jpg"]
    assert captured["user"]["productionContext"]["requestedEditWindow"]["inspectionFrames"] == 3
    assert result["reply"]["editStartSec"] == 8.5
    assert result["messages"][-1]["editEndSec"] == 11
    assert result["zeroMediaSpend"] is True
