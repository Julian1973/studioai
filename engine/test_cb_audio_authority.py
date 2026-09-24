import cb_audio_authority as A
from copy import deepcopy
import hashlib
import pytest
from studio_source_segmentation import project


def segmented(raw, speech):
    row = line(raw)
    boundary = len(speech)
    row['sourceSegmentation'] = project(row, raw, boundary={
        'scriptRevision': 'sha256:' + hashlib.sha256(raw.encode()).hexdigest(),
        'occurrenceId': row['dialogueOccurrenceId'], 'speaker': row['speaker'],
        'authority': 'reviewed_source_boundaries', 'evidenceId': 'test-reviewed-boundary',
        'spans': {'spokenText': [0, boundary], 'actionAfter': [boundary + 1, len(raw)]}})
    return row


@pytest.mark.parametrize('raw,speech', [
    ('A little sprinkle is good luck, right? Another drop hits a lantern.',
     'A little sprinkle is good luck, right?'),
    ('It’s fine! It’s okay! Everything is fine! Then the sky opens up. Rain pours over the decorations.',
     'It’s fine! It’s okay! Everything is fine!'),
    ('Not good luck! It’s not fine! Save the berry cups! A lantern flickers. PSSST. Out.',
     'Not good luck! It’s not fine! Save the berry cups!'),
])
def test_verified_source_action_never_becomes_speech_or_character_laughter(raw, speech):
    source = segmented(raw, speech)
    before = deepcopy(source)
    routed = A.route_lines([source])
    assert routed['spokenDialogue'][0]['exactText'] == speech
    assert routed['spokenDialogue'][0]['scriptExactText'] == raw
    assert routed['seedanceSfxCues'] == []
    assert source == before
    direction = {'lines': [{'dialogueOccurrenceId': source['dialogueOccurrenceId'],
                           'exactDialogue': raw, 'performedText': '[nervous] ' + raw}]}
    output, _ = A.route_voice_direction(direction, [source])
    assert output['lines'][0]['exactDialogue'] == speech
    assert output['lines'][0]['performedText'] == '[nervous] ' + speech


def test_invalid_segmentation_cannot_fall_back_to_legacy_guess():
    source = segmented('Hello. Rain falls.', 'Hello.')
    source['exactText'] = 'Changed words. Rain falls.'
    with pytest.raises(ValueError, match='source payload changed'):
        A.route_line(source)


def test_verified_source_payload_survives_provider_name_casing_normalisation():
    raw = 'It’s fine! Then SUNNY rushes around trying to fix everything.'
    source = segmented(raw, 'It’s fine!')
    routed = __import__('cb_departments').provider_audio_routing({
        'charactersInFrame': ['Sunny'], 'dialogueLines': [source]
    })
    assert routed['spokenDialogue'][0]['exactText'] == 'It’s fine!'
    assert routed['spokenDialogue'][0]['scriptExactText'] == raw


def test_scoped_source_span_keeps_screenplay_action_out_of_voice():
    import cb_intake
    import cb_render

    script = (
        'INT. PARTY CAVE - DAY 4\n\n'
        'KEEN\nOh… no sunshine today? Just a drop?\n\n'
        'Instead of calming down, Sunny throws her hands in the air.\n\n'
        'SUNNY\nOh no! I’m making it rain inside!\n\n'
        'She lets go of the wet garland.\n'
    )
    parsed = cb_intake.parse_script(script, ['Keen', 'Sunny'], log=lambda *_: None)
    cb_intake._annotate_source_events(parsed['events'], 'sha256:' + hashlib.sha256(
        script.encode()).hexdigest())
    voices = []
    for event in parsed['events']:
        if event['type'] != 'dialogue':
            continue
        row = {'dialogueOccurrenceId': event['dialogueOccurrenceId'],
               'speaker': event['speaker'], 'exactText': event['text'],
               'sourceSegmentation': cb_render._structural_spoken_source(event, script)}
        voices.append(A.route_line(row)[0]['exactText'])
    assert voices == ['Oh… no sunshine today? Just a drop?',
                      'Oh no! I’m making it rain inside!']
    assert [event['text'] for event in parsed['events'] if event['type'] == 'action'] == [
        'Instead of calming down, Sunny throws her hands in the air.',
        'She lets go of the wet garland.']


def test_legacy_lantern_action_does_not_invent_laughter():
    spoken, cue = A.route_line(line('A little sprinkle is good luck, right? Another drop hits a lantern.'))
    assert spoken['exactText'] == 'A little sprinkle is good luck, right?'
    assert cue is None


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


def test_performance_projection_accepts_typographic_apostrophe_without_changing_words():
    candidate = "[nervous] I can’t see!"
    assert A._project_performed_text(candidate, "I can't see!") == candidate


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
