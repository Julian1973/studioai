import cb_audio_authority as A


def line(text, start=1, end=2):
    return {"speaker": "Fuzzby", "exactText": text, "startSec": start,
            "endSec": end, "dialogueOccurrenceId": text}


def test_pure_snore_routes_only_to_seedance_sfx():
    routed = A.route_lines([line("ZZZZZ …")])
    assert routed["spokenDialogue"] == []
    assert routed["seedanceSfxCues"][0]["kinds"] == ["snore"]
    assert routed["seedanceSfxCues"][0]["sourceDialogueIndex"] == 1
    assert "Do not synthesize words" in routed["seedanceSfxCues"][0]["instruction"]


def test_pure_sneeze_never_reaches_elevenlabs():
    routed = A.route_lines([line("AHHHHCHHOOOOO!!! AHHHHCHHOOOOO!!!")])
    assert routed["spokenDialogue"] == []
    assert routed["seedanceSfxCues"][0]["kinds"] == ["sneeze"]


def test_mixed_line_keeps_words_and_routes_sneeze_separately():
    routed = A.route_lines([line("Oh, Ah, Hi Fuzzby … ACHOO!")])
    assert routed["spokenDialogue"][0]["exactText"] == "Oh, Ah, Hi Fuzzby…"
    assert routed["spokenDialogue"][0]["sfxInterrupted"] is True
    assert routed["spokenDialogue"][0]["scriptExactText"] == "Oh, Ah, Hi Fuzzby … ACHOO!"
    assert routed["seedanceSfxCues"][0]["kinds"] == ["sneeze"]


def test_script_number_and_trailing_stage_note_are_not_spoken_or_routed_as_sfx():
    source = line("7\tSomeone needs a little help today. (AIDA reacts to off camera SNEEZE)")
    source["delivery"] = "Begin after the sneeze lands, then speak with quiet warmth."
    routed = A.route_lines([source])

    assert routed["spokenDialogue"][0]["exactText"] == "Someone needs a little help today."
    assert routed["spokenDialogue"][0]["scriptExactText"] == source["exactText"]
    assert routed["spokenDialogue"][0]["delivery"] == source["delivery"]
    assert routed["seedanceSfxCues"] == []


def test_mixed_line_preserves_delivery_prose_that_mentions_the_sfx():
    source = line("Coming, Aida! AHHHHCHHOOOOO!!!")
    source["delivery"] = "The sneeze steals Keen's confidence after the spoken answer."
    routed = A.route_lines([source])

    assert routed["spokenDialogue"][0]["exactText"] == "Coming, Aida!"
    assert routed["spokenDialogue"][0]["delivery"] == source["delivery"]
    assert routed["seedanceSfxCues"][0]["kinds"] == ["sneeze"]


def test_leading_sneeze_stays_verbatim_in_audio1_before_spoken_words():
    routed = A.route_lines([line("ACHOO! … Oh, Ah, Hi Fuzzby")])
    assert routed["spokenDialogue"][0]["exactText"] == "ACHOO! … Oh, Ah, Hi Fuzzby"
    assert routed["spokenDialogue"][0]["sfxEmbeddedInDialogue"] is True
    assert routed["seedanceSfxCues"] == []


def test_leading_sneeze_after_performance_tag_stays_in_audio1():
    source = "[gasps] ACHOO! … Oh, Ah, Hi Fuzzby"
    spoken, cue = A.route_line(line(source))
    assert spoken["exactText"] == source
    assert cue is None


def test_spoken_dialogue_is_unchanged():
    routed = A.route_lines([line("Never … Ever?")])
    assert routed["spokenDialogue"][0]["exactText"] == "Never … Ever?"
    assert routed["seedanceSfxCues"] == []


def test_laughter_woven_through_spoken_words_stays_in_audio1():
    source = "[laughs] You will never, ever, ever get my honeycomb."
    routed = A.route_lines([line(source)])
    assert routed["spokenDialogue"][0]["exactText"] == source
    assert routed["spokenDialogue"][0]["sfxEmbeddedInDialogue"] is True
    assert routed["seedanceSfxCues"] == []


def test_standalone_laughter_remains_seedance_sfx():
    routed = A.route_lines([line("[laughs]")])
    assert routed["spokenDialogue"] == []
    assert routed["seedanceSfxCues"][0]["kinds"] == ["laughter"]


def test_trailing_third_person_giggle_routes_out_of_spoken_dialogue():
    source = line("3,2,1… POOF! The tail does ‘The Thing’ again and again. Bo giggles.")
    source["speaker"] = "Bo"

    routed = A.route_lines([source])

    assert routed["spokenDialogue"][0]["exactText"] == "3,2,1…"
    assert routed["seedanceSfxCues"][0]["kinds"] == ["laughter"]
    assert routed["seedanceSfxCues"][0]["authoredCue"] == (
        "POOF! The tail does ‘The Thing’ again and again. Bo giggles.")


def test_screenplay_action_and_beat_are_never_sent_as_spoken_words():
    routed = A.route_lines([
        line("3,2,1 … POOF! The tail does ‘The Thing’ again and again. Bo giggles."),
        line("They all know each other. Beat. But I don’t know them."),
        line("Every single time. BEAT."),
    ])

    assert [item["exactText"] for item in routed["spokenDialogue"]] == [
        "3,2,1…",
        "They all know each other. But I don’t know them.",
        "Every single time.",
    ]
    assert routed["seedanceSfxCues"][0]["authoredCue"].startswith("POOF!")


def test_existing_voice_direction_is_projected_to_spoken_lane_without_laugh_tag():
    source = line("3,2,1… POOF! The tail does ‘The Thing’ again and again. Bo giggles.")
    source["speaker"] = "Bo"
    direction = {"lines": [{
        "dialogueOccurrenceId": source["dialogueOccurrenceId"],
        "exactDialogue": source["exactText"],
        "performedText": (
            "[playfully] 3,2,1… POOF! The tail does ‘The Thing’ again and again. "
            "[laughs] Bo"),
        "takeRecipes": [{
            "performedText": (
                "[playfully] 3,2,1… POOF! The tail does ‘The Thing’ again and again. "
                "[laughs] Bo")
        }],
    }]}

    projected, spoken = A.route_voice_direction(direction, [source])

    expected = "[playfully] 3,2,1…"
    assert spoken[0]["exactText"] == "3,2,1…"
    assert projected["lines"][0]["performedText"] == expected
    assert projected["lines"][0]["takeRecipes"][0]["performedText"] == expected


def test_sustained_meditation_tone_routes_only_to_seedance_sfx():
    source = line("oooohhhhhhhhmmmmmmmmmmmm", start=6.0, end=10.5)
    source["speaker"] = "Zenny"
    routed = A.route_lines([source])

    assert routed["spokenDialogue"] == []
    cue = routed["seedanceSfxCues"][0]
    assert cue["character"] == "Zenny"
    assert cue["kinds"] == ["meditation mantra chant"]
    assert cue["startSec"] == 6.0
    assert cue["endSec"] == 10.5
    assert cue["authoredCue"] == "oooohhhhhhhhmmmmmmmmmmmm"
    assert 'meditation mantra chant of "Ohhmmmmmm"' in cue["instruction"]
    assert "one continuous, warm, unstrained ooh-to-mmm tone" in cue["instruction"]
    assert "Do not synthesize words" in cue["instruction"]


def test_legacy_direction_without_occurrence_ids_is_untouched_without_sfx():
    direction = {"lines": [{"exactDialogue": "Nailed it.", "performedText": "Nailed it."}]}
    projected, spoken = A.route_voice_direction(direction, [line("Nailed it.")])
    assert projected == direction
    assert spoken[0]["exactText"] == "Nailed it."
