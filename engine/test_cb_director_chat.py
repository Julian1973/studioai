import json
from pathlib import Path

import cb_director_chat as chat


def test_applied_director_instruction_keeps_visible_result_and_removes_stale_slot_claim():
    instruction = chat.production_instruction({
        "correction": "Place Keen screen-left.",
        "changeSummary": "Sunny lifts the garland. Use @图6 as continuity reference.",
        "protectedElements": ["Keep the approved room lighting."],
    })
    assert "Place Keen screen-left." in instruction
    assert "Visible result required: Sunny lifts the garland." in instruction
    assert "the supplied reference as continuity reference" in instruction
    assert "@图6" not in instruction
    assert "Keep locked: Keep the approved room lighting." in instruction
    source = (Path(__file__).resolve().parents[1] / "cb-studio" / "serve.py").read_text(encoding="utf-8")
    assert "correction = cb_director_chat.production_instruction(latest)" in source


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
    assert captured["kwargs"]["reasoning_effort"] == chat.CHAT_REASONING
    assert captured["kwargs"]["max_output_tokens"] == chat.CHAT_MAX_OUTPUT_TOKENS
    assert captured["user"]["productionContext"]["exactDialogue"][0]["exactText"] == "Today could be OK."
    assert captured["user"]["productionContext"]["orderedShotStates"]["opening"] == "Bo holds the conker at the satchel."
    assert "accept ONE plain creative note" in captured["system"]
    assert "Never rewrite exact dialogue" in captured["system"]
    assert "Scene coverage precedes generation planning" in captured["system"]
    assert "Keep one coherent camera treatment" not in captured["system"]
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


def test_chat_preserves_acting_coverage_and_dialogue_timing_authorities(monkeypatch, tmp_path):
    import copy
    package = _package()
    shot = package["shots"][0]
    shot.update({
        "durationSec": 30,
        "performanceContractApproved": {"listener": "Keep attention on the held conker; settle weight before looking up."},
        "cinematographyContractApproved": {"purpose": "Reveal the friend's understanding."},
        "comedyContractsApproved": [{"payoff": "The listener notices the hidden conker."}],
        "emotionContractsApproved": [{"change": "Concern softens into understanding."}],
        "storyboardInternalShotPlanApproved": [{"viewId": "reaction", "transitionType": "cut", "subject": "listening friend"}],
    })
    shot["dialogueLines"][0].update(dialogueOccurrenceId="line-1", startSec=7.2, endSec=9.1)
    package["sourceStoryboard"] = {"sha256": "approved-storyboard"}
    package["continuityLedger"][0]["voiceApproval"] = {"approved": True, "path": "/approved/voice.wav"}
    original = copy.deepcopy(package)
    monkeypatch.setattr(chat.cb_render, "load_pkg", lambda scene, episode: (package, tmp_path / "pkg.json"))

    context = chat._scope_context("Ep2", "1", "S1.SH1", "animation", "Make the listener's thought readable.")

    assert context["stageDirection"]["performanceContractApproved"] == shot["performanceContractApproved"]
    assert context["stageDirection"]["emotionContractsApproved"] == shot["emotionContractsApproved"]
    assert context["stageDirection"]["comedyContractsApproved"] == shot["comedyContractsApproved"]
    assert context["stageDirection"]["storyboardInternalShotPlanApproved"][0]["transitionType"] == "cut"
    assert context["directorCardRevision"]["sourceBindings"]["voiceApproval"]["path"] == "/approved/voice.wav"
    assert context["exactDialogue"][0]["startSec"] == 7.2
    assert context["exactDialogue"][0]["endSec"] == 9.1
    assert context["exactDialogue"][0]["exactText"] == "Today could be OK."
    assert "singleCameraTreatment" not in context
    assert package == original


def test_director_repair_context_uses_hash_verified_approved_audio1_timing(monkeypatch, tmp_path):
    import hashlib

    package = _package()
    shot = package["shots"][0]
    shot.update(durationSec=30)
    shot["dialogueLines"][0].update(
        dialogueOccurrenceId="line-1", startSec=7.2, endSec=33.46)
    audio = tmp_path / "approved.wav"
    audio.write_bytes(b"approved audio bytes")
    timing = tmp_path / "timing.json"
    timing.write_text("{}", encoding="utf-8")
    receipt = tmp_path / "placement.json"
    receipt.write_text(json.dumps({
        "outputPath": str(audio),
        "outputSha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
        "dialogueTimingPath": str(timing),
        "dialogueTimingSha256": hashlib.sha256(timing.read_bytes()).hexdigest(),
        "placements": [{"dialogueOccurrenceId": "line-1", "targetStartSec": 7.4,
                        "targetEndSec": 9.25}],
    }), encoding="utf-8")
    package["continuityLedger"][0].update(
        voiceApproval={"approved": True, "path": str(audio)},
        voPlacementPath=str(receipt))
    monkeypatch.setattr(chat.cb_render, "load_pkg", lambda scene, episode: (package, tmp_path / "pkg.json"))

    context = chat._scope_context("Ep2", "1", "S1.SH1", "storyboard", "Fix stale timing")

    assert context["exactDialogue"][0]["startSec"] == 7.4
    assert context["exactDialogue"][0]["endSec"] == 9.25
    assert context["verifiedApprovedAudio1Intervals"][0]["measured"]["endSec"] == 9.25
    assert "override every estimate, raw script interval, or prior conversation claim" in context["timingScope"]
    assert shot["dialogueLines"][0]["endSec"] == 33.46


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


def test_chat_reads_the_typed_closing_state_and_never_treats_prose_continuity_as_a_record(monkeypatch, tmp_path):
    """Real packages carry continuityOut as prose (str) and the typed state in
    continuityOutState. The chat used to call .get on the prose and stop every Director
    conversation with "'str' object has no attribute 'get'" (Ep4 scene 2, 19 Sep)."""
    package = _package()
    shot = package["shots"][0]
    shot["continuityOut"] = "Aida holds the conker at the satchel, camera side left, lantern light."
    shot["continuityOutState"] = {"cameraSide": "left", "lighting": "lantern",
                                  "characters": [{"character": "Aida", "screenZone": "left", "pose": "seated", "expression": "warm"}]}
    monkeypatch.setattr(chat.cb_render, "load_pkg", lambda scene, episode: (package, tmp_path / "pkg.json"))
    context = chat._scope_context("Ep4", "2", "S1.SH1", "animation", "Open on the world.")
    landing = context["orderedShotStates"]["landing"]
    assert landing["cameraSide"] == "left" and landing["characters"][0]["character"] == "Aida"
    assert landing["description"].startswith("Aida holds the conker")
    shot.pop("continuityOutState")
    context = chat._scope_context("Ep4", "2", "S1.SH1", "animation", "Open on the world.")
    assert context["orderedShotStates"]["landing"]["characters"] == []
