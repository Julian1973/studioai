from cb_render import _explicit_voice_correction_overrides as overrides

def test_word_only_correction_does_not_override_director():
    assert overrides([{'exactText':'Ow!'}],[{'dialogueOccurrenceId':'a','sourceEventId':'b','speaker':'Keen'}]) == []

def test_explicit_performance_is_preserved_including_plain_text():
    normalized=[{'dialogueOccurrenceId':'a','sourceEventId':'b','speaker':'Keen'}]
    for text in ['[quietly] Ow!', 'Ow!']:
        assert overrides([{'performanceText':text}],normalized)[0]['text']==text
