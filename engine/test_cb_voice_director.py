import copy
import json

import pytest

import cb_voice_director as V


LOCKED = {
    "dialogueOccurrenceId": "occ-1", "sourceEventId": "event-1",
    "speaker": "Fuzzby", "exactText": "Nailed it.",
}


def direction():
    return {
        "dialogueOccurrenceId": "occ-1", "sourceEventId": "event-1",
        "character": "Fuzzby", "exactDialogue": "Nailed it.",
        "archetypeId": "false-triumph-button",
        "performanceQuestions": {
            "intention": "Win Zenny's admiration.",
            "subtext": "Hide the crash.",
            "thoughtBefore": "Hold the pose.",
            "changeDuring": "Impact breath becomes authority.",
            "operativeWords": ["Nailed"],
        },
        "physicalState": "Chest out, still wobbling.",
        "emotionalState": {"entry": "Winded", "exit": "Proud"},
        "listener": "Zenny", "bodyVoiceRelationship": "Voice contradicts the crash.",
        "previousText": "BIZZY-BIZZY-BIZZY...",
        "startsAtSec": 0.4, "estimatedDurationSec": 1.0,
        "pauseReasons": [],
        "tagPurposes": {
            "exhales": "Converts the impact breath into triumph.",
            "confident": "Makes the claim land as authority.",
            "breathes": "Keeps the impact physically present.",
            "proud": "Puts status on the operative word.",
            "casual": "Attempts to minimise the visible failure.",
        },
        "takeRecipes": [
            {"recipeId": "A", "label": "Julian's pick",
             "performedText": "[exhales][confident] Nailed it.",
             "primary": True, "takesCount": 3},
            {"recipeId": "B", "label": "Proud emphasis",
             "performedText": "[breathes][proud] NAILED it.",
             "takesCount": 3},
            {"recipeId": "C", "label": "Casual cover",
             "performedText": "[casual] Nailed it.", "takesCount": 3},
        ],
    }


def test_compiler_emits_nine_stable_v3_requests_with_canon_settings():
    compiled = V.compile_line(direction(), LOCKED)
    first = V.emit_v3_requests(compiled)
    second = V.emit_v3_requests(compiled)
    assert first == second
    assert len(first) == 9
    assert [(item["recipeId"], item["takeNumber"]) for item in first] == [
        (recipe, take) for recipe in ("A", "B", "C") for take in (1, 2, 3)]
    assert first[0]["body"]["model_id"] == "eleven_v3"
    assert first[0]["body"]["voice_settings"] == {
        "stability": 0.25, "similarity_boost": 0.7, "style": 0.4}
    assert "previous_text" not in first[0]["body"]
    assert first[0]["contextRunway"] == "BIZZY-BIZZY-BIZZY..."
    assert "does not accept previous_text" in first[0]["transportNotes"][0]


@pytest.mark.parametrize("mutation,match", [
    (lambda item: item["performanceQuestions"].pop("thoughtBefore"),
     "Missing performance questions"),
    (lambda item: item["takeRecipes"][0].update(
        {"performedText": "[exhales][confident] Totally nailed it."}),
     "must preserve every locked script word"),
    (lambda item: item["takeRecipes"][0].update(
        {"performedText": "[exhales][confident][angry] Nailed it."}),
     "off-palette/banned tags"),
    (lambda item: item.update({"previousText": ""}),
     "previous_text runway"),
])
def test_post_direction_audit_hard_blocks_rulebook_failures(mutation, match):
    item = copy.deepcopy(direction())
    mutation(item)
    with pytest.raises(V.VoiceContractError, match=match):
        V.compile_line(item, LOCKED)


def test_track_refuses_an_uncovered_locked_line():
    with pytest.raises(V.VoiceContractError, match="script locks 2"):
        V.compile_track({"shotId": "S1.SH1A", "lines": [direction()]},
                        [LOCKED, {**LOCKED, "dialogueOccurrenceId": "occ-2"}])


def test_voice_path_rejects_a_dangling_performed_sentence():
    item = copy.deepcopy(direction())
    item["takeRecipes"][0]["performedText"] = "[exhales][confident] Nailed it"
    with pytest.raises(V.VoiceContractError, match="complete spoken sentence"):
        V.compile_line(item, LOCKED)


def test_voice_path_preserves_intentionally_unpunctuated_locked_dialogue():
    locked = {**LOCKED, "exactText": "ACHOO! … Oh, Ah, Hi Fuzzby"}
    item = copy.deepcopy(direction())
    item["exactDialogue"] = locked["exactText"]
    item["takeRecipes"] = [{**item["takeRecipes"][0],
                             "performedText": "[exhales] ACHOO! … Oh, Ah, Hi Fuzzby"}]
    item["pauseReasons"] = ["The ellipsis holds Keen's embarrassed recovery after the sneeze."]
    compiled = V.compile_line(item, locked)
    assert V.emit_v3_requests(compiled)[0]["body"]["text"].endswith("Hi Fuzzby")


def test_voice_path_excludes_script_number_and_trailing_stage_note_from_speech():
    locked = {
        **LOCKED,
        "speaker": "Aida",
        "exactText": "7\tSomeone needs a little help today. (AIDA reacts to off camera SNEEZE)",
    }
    item = copy.deepcopy(direction())
    item.update({
        "character": "Aida",
        "exactDialogue": locked["exactText"],
        "estimatedDurationSec": 2.0,
    })
    item["takeRecipes"] = [{
        **item["takeRecipes"][0],
        "recipeId": "S2.SH2.Aida.01.primary",
        "performedText": "[exhales] Someone needs a little help today.",
    }]

    compiled = V.compile_line(item, locked)
    assert compiled["exactDialogue"] == locked["exactText"]
    assert V.emit_v3_requests(compiled)[0]["body"]["text"].endswith(
        "Someone needs a little help today.")

    item["takeRecipes"][0]["performedText"] = (
        "[exhales] Someone needs a lot of help today.")
    with pytest.raises(V.VoiceContractError, match="must preserve every locked script word"):
        V.compile_line(item, locked)


def test_voice_path_preserves_a_scripted_interruption():
    locked = {**LOCKED, "exactText": "I am extremely—"}
    item = copy.deepcopy(direction())
    item["exactDialogue"] = "I am extremely—"
    item["takeRecipes"] = [{**item["takeRecipes"][0],
                             "performedText": "[exhales][confident] I am extremely—"}]
    item["pauseReasons"] = ["The dash is an interruption caused by a visible discovery."]
    compiled = V.compile_line(item, locked)
    requests = V.emit_v3_requests(compiled)
    assert requests[0]["body"]["text"] == "[exhales][confident] I am extremely—"


def test_group_chorus_binds_every_named_canon_voice():
    locked = {
        **LOCKED,
        "speaker": "ALL",
        "voiceTreatment": "group_chorus",
        "chorusMembers": ["Aida", "Amie", "Howey"],
    }
    item = copy.deepcopy(direction())
    item.update({"character": "ALL", "speaker": "ALL"})
    compiled = V.compile_line(item, locked)
    cards = V.voice_cards()["characters"]
    assert compiled["voiceTreatment"] == "group_chorus"
    assert compiled["chorusMembers"] == ["Aida", "Amie", "Howey"]
    assert compiled["voiceIds"] == [
        cards[name]["voiceId"] for name in ("Aida", "Amie", "Howey")]


def test_bo_has_canon_voice_card_matching_character_registry():
    card = V.voice_cards()["characters"]["Bo"]
    character = json.loads(
        (V.ROOT / "projects/crystal-bears/canon/characters.json").read_text(
            encoding="utf-8"))["Bo"]

    assert card["voiceId"] == "AAF2q3NCwTrLMMkEnRLB"
    assert card["voiceId"] == character["voiceId"]
