from copy import deepcopy
import cb_voice_director as V
import cb_handover as H


def test_direct_preserves_inline_emotional_turn_and_exact_dialogue(monkeypatch):
    monkeypatch.setattr(V, 'voice_cards', lambda: {'characters': {
        'Sunny': {'voiceId': 'fixture', 'settings': {}, 'modelId': 'eleven_v3'}}})
    line = {'dialogueOccurrenceId': 'occ', 'speaker': 'Sunny',
            'exactText': 'I can do this. Can I?'}
    brief = {'dialogueOccurrenceId': 'occ', 'elevenLabsV3Direction':
             '[confident] I can do this. [ nervous] Can I?',
             'dramaticIntention': 'Reassure herself as certainty slips.'}
    shot = {'shotId': 'test', 'voiceDirectorBrief': [brief]}
    before = deepcopy(shot)
    item = V.compile_direct_track(shot, [line])['lines'][0]
    assert item['takeRecipes'][0]['performedText'] == '[confident] I can do this. [nervous] Can I?'
    assert item['performanceNotes']['dramaticIntention'] == brief['dramaticIntention']
    assert item['performanceWarning'] is None
    assert shot == before


def test_legacy_acting_prose_is_flagged_not_spoken(monkeypatch):
    monkeypatch.setattr(V, 'voice_cards', lambda: {'characters': {
        'Sunny': {'voiceId': 'fixture', 'settings': {}}}})
    line = {'dialogueOccurrenceId': 'occ', 'speaker': 'Sunny', 'exactText': 'Hello.'}
    shot = {'shotId': 'test', 'voiceDirectorBrief': [{'dialogueOccurrenceId': 'occ',
            'elevenLabsV3Direction': 'Hide anxiety with a small confident greeting.'}]}
    item = V.compile_direct_track(shot, [line])['lines'][0]
    assert item['takeRecipes'][0]['performedText'] == 'Hello.'
    assert item['performanceWarning']


def test_plain_dialogue_with_authored_emotional_turn_is_flagged(monkeypatch):
    monkeypatch.setattr(V, 'voice_cards', lambda: {'characters': {
        'Keen': {'voiceId': 'fixture', 'settings': {}}}})
    line = {'dialogueOccurrenceId': 'occ', 'speaker': 'Keen',
            'exactText': 'Actually… don’t worry!'}
    shot = {'shotId': 'test', 'voiceDirectorBrief': [{
        'dialogueOccurrenceId': 'occ',
        'elevenLabsV3Direction': line['exactText'],
        'emotionalEntry': 'Surprised', 'emotionalExit': 'Reassuring'}]}
    item = V.compile_direct_track(shot, [line])['lines'][0]
    assert item['takeRecipes'][0]['performedText'] == line['exactText']
    assert 'no vocal cue' in item['performanceWarning']


def test_handover_retains_emotional_intent():
    source = {'dialogueOccurrenceId': 'occ', 'sourceEventId': 'event', 'speaker': 'Sunny',
              'exactDialogue': 'Hello.', 'elevenLabsV3Direction': '[shy] Hello.',
              'emotionalEntry': 'Uncertain', 'emotionalExit': 'Hopeful',
              'dramaticIntention': 'Ask to join', 'pace': 'Tentative', 'subtext': 'Will you accept me?'}
    result = H._voice_director_brief_lines([source])[0]
    for key in ('emotionalEntry', 'emotionalExit', 'dramaticIntention', 'pace', 'subtext'):
        assert result[key] == source[key]
