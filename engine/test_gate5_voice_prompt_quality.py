from types import SimpleNamespace

import cb_creative as creative
import cb_voice_director


def test_luna_repair_moves_authored_turn_into_exact_provider_text(monkeypatch):
    occurrence = "dialogue-occurrence:sha256:test-keen"
    exact = "Oh… no sunshine today? Just a drop?"
    voice = creative.VoicePerformance(
        dialogueOccurrenceId=occurrence, speaker="Keen", exactDialogue=exact,
        dramaticIntention="Make the drip feel harmless", subtext="Do not alarm Sunny",
        relationshipTarget="Sunny", emotionalEntry="Curious",
        emotionalExit="Concerned", operativeWords=["drop"], pace="Light, then careful",
        rhythm="Joke, then check", pauses="Pause after the question",
        breaths="Small breath", nonVerbalActions="Look up",
        elevenLabsV3Direction=exact, physicalActionRelationship="Watch Sunny",
        expectedTiming="0–3s")
    locked = {"dialogueOccurrenceId": occurrence, "sourceEventId": "event-1",
              "sourceEventIndex": 7, "beatId": "4.B1", "sourceBeatId": "source-1",
              "speaker": "Keen", "exactText": exact}
    monkeypatch.setattr(creative, "_script_beats", lambda *_: ([{}], {}))
    monkeypatch.setattr(creative, "_locked_dialogue", lambda _: [locked])
    monkeypatch.setattr(creative, "_mind", lambda *_: "Voice Director")
    monkeypatch.setattr(cb_voice_director, "voice_cards", lambda: {"characters": {
        "Keen": {"cadenceSignature": "Curious, then careful",
                 "defaultTags": ["curious", "nervous"], "bannedTags": []}}})
    calls = []

    def luna(_system, user, schema, **_kwargs):
        calls.append((user, schema))
        if schema is creative.VoiceScript:
            return creative.VoiceScript(performances=[voice])
        assert schema is creative.VoicePromptRepair
        return creative.VoicePromptRepair(lines=[creative.VoicePromptRepairLine(
            dialogueOccurrenceId=occurrence,
            elevenLabsV3Direction=(
                "[curious] Oh… no sunshine today? [nervous] Just a drop?"))])

    monkeypatch.setattr(creative.cb_llm, "structured", luna)
    scene = SimpleNamespace(model_dump=lambda include: {
        "purpose": "Sunny wants a perfect party"})
    beat = SimpleNamespace(model_dump=lambda include: {
        "consequence": "The wet garland drips on Keen"})
    direction = SimpleNamespace(scene=scene, beats=[beat])
    shot = SimpleNamespace(
        shotId="S4.SH2", purpose="Show Sunny's fix making things wetter",
        audienceExperience="Concern, then warmth", principalPerformance="Keen reassures",
        physicalPerformance="Keen blinks under the drip", animationTiming="Pause")
    result = creative.gate5_voice("Ep4", 4, direction, [shot], log=lambda *_: None)

    assert len(calls) == 2
    assert "Sunny wants a perfect party" in calls[0][0]
    assert "The wet garland drips on Keen" in calls[0][0]
    assert result[0].elevenLabsV3Direction == (
        "[curious] Oh… no sunshine today? [nervous] Just a drop?")
    assert result[0].exactDialogue == exact


def test_luna_repair_cannot_change_spoken_words(monkeypatch):
    occurrence = "dialogue-occurrence:sha256:test"
    voice = creative.VoicePerformance(
        dialogueOccurrenceId=occurrence, speaker="Keen", exactDialogue="Just a drop?",
        dramaticIntention="Reassure", subtext="Do not alarm Sunny",
        relationshipTarget="Sunny", emotionalEntry="Curious", emotionalExit="Worried",
        operativeWords=["drop"], pace="Light", rhythm="Quick", pauses="Brief",
        breaths="Natural", nonVerbalActions="None",
        elevenLabsV3Direction="Just a drop?", physicalActionRelationship="Looks up",
        expectedTiming="1s")
    locked = {"dialogueOccurrenceId": occurrence, "sourceEventId": "event-1",
              "sourceEventIndex": 1, "beatId": "4.B1", "sourceBeatId": "source-1",
              "speaker": "Keen", "exactText": "Just a drop?"}
    monkeypatch.setattr(creative, "_script_beats", lambda *_: ([{}], {}))
    monkeypatch.setattr(creative, "_locked_dialogue", lambda _: [locked])
    monkeypatch.setattr(creative, "_mind", lambda *_: "Voice Director")
    monkeypatch.setattr(cb_voice_director, "voice_cards", lambda: {"characters": {
        "Keen": {"defaultTags": ["curious"], "bannedTags": []}}})

    def luna(_system, _user, schema, **_kwargs):
        if schema is creative.VoiceScript:
            return creative.VoiceScript(performances=[voice])
        return creative.VoicePromptRepair(lines=[creative.VoicePromptRepairLine(
            dialogueOccurrenceId=occurrence,
            elevenLabsV3Direction="[curious] Just a BIG drop?")])

    monkeypatch.setattr(creative.cb_llm, "structured", luna)
    shot = SimpleNamespace(
        shotId="S4.SH2", purpose="A drip", audienceExperience="Warmth",
        principalPerformance="Reassure", physicalPerformance="Blink",
        animationTiming="Pause")
    result = creative.gate5_voice("Ep4", 4, None, [shot], log=lambda *_: None)
    assert result[0].elevenLabsV3Direction == "Just a drop?"


def test_luna_repair_replaces_prose_without_speaking_it(monkeypatch):
    occurrence = "dialogue-occurrence:sha256:test-prose"
    exact = "Just a drop?"
    voice = creative.VoicePerformance(
        dialogueOccurrenceId=occurrence, speaker="Keen", exactDialogue=exact,
        dramaticIntention="Reassure", subtext="Do not alarm Sunny",
        relationshipTarget="Sunny", emotionalEntry="Curious", emotionalExit="Curious",
        operativeWords=["drop"], pace="Light", rhythm="Quick", pauses="Brief",
        breaths="Natural", nonVerbalActions="None",
        elevenLabsV3Direction="Say this gently while looking up: Just a drop?",
        physicalActionRelationship="Looks up", expectedTiming="1s")
    locked = {"dialogueOccurrenceId": occurrence, "sourceEventId": "event-1",
              "sourceEventIndex": 1, "beatId": "4.B1", "sourceBeatId": "source-1",
              "speaker": "Keen", "exactText": exact}
    monkeypatch.setattr(creative, "_script_beats", lambda *_: ([{}], {}))
    monkeypatch.setattr(creative, "_locked_dialogue", lambda _: [locked])
    monkeypatch.setattr(creative, "_mind", lambda *_: "Voice Director")
    monkeypatch.setattr(cb_voice_director, "voice_cards", lambda: {"characters": {
        "Keen": {"defaultTags": ["curious"], "bannedTags": []}}})
    schemas = []

    def luna(_system, _user, schema, **_kwargs):
        schemas.append(schema)
        if schema is creative.VoiceScript:
            return creative.VoiceScript(performances=[voice])
        return creative.VoicePromptRepair(lines=[creative.VoicePromptRepairLine(
            dialogueOccurrenceId=occurrence,
            elevenLabsV3Direction="[curious] Just a drop?")])

    monkeypatch.setattr(creative.cb_llm, "structured", luna)
    shot = SimpleNamespace(shotId="S4.SH2", purpose="A drip", audienceExperience="Warmth",
                           principalPerformance="Reassure", physicalPerformance="Blink",
                           animationTiming="Pause")
    result = creative.gate5_voice("Ep4", 4, None, [shot], log=lambda *_: None)
    assert schemas == [creative.VoiceScript, creative.VoicePromptRepair]
    assert result[0].elevenLabsV3Direction == "[curious] Just a drop?"
