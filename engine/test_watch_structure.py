"""Offline contract checks, not a claim that generated performances will land."""
from copy import deepcopy
import re
from test_studio_storyboard_prompt import example
import cb_departments as D
from studio_watch_structure import apply, VERSION


def test_native_payload_uses_current_start_end_and_protects_exact_dialogue():
    shot, direction = example()
    direction['physicalCauseAndEffect'] = 'Mira releases the cup only after Oren supports its weight.'
    before = deepcopy((shot, direction))
    prompt = D.compile_animation_provider_prompt(shot, direction)
    assert prompt.startswith('[PURPOSE]')
    assert '[REFERENCE AUTHORITY]' in prompt and '[TIMED ACTION]' in prompt
    assert '[OPENING STATE]\nMira holds a cup.' in prompt
    assert '[CONTINUITY OUT]\nOren holds the cup.' in prompt
    assert '[CAUSALITY]\n' + direction['physicalCauseAndEffect'] in prompt
    assert prompt.count('{Here you are.}') == 1
    from cb_emission_conformance import dialogue_cues, dialogue_placement_line
    assert dialogue_placement_line(dialogue_cues(shot['dialogueLines'], duration_sec=8)[0], hold_after=False) in prompt
    assert 'Shot 1: 0–4s' in prompt and 'Shot 2: 4–8s' in prompt
    assert 'Aida' not in prompt and '13 seconds' not in prompt
    assert (shot, direction) == before


def test_presentation_is_idempotent_and_keeps_audio_and_authored_sfx_verbatim():
    audio = '[Audio]\n@Audio1 exact approved bed; Fuzzby laughs as authored Seedance SFX.'
    prompt = '[Audience Purpose]\nA surprise.\n\n[Shot Sequence]\nShot 1: 0–20s\nAction: Fuzzby wakes.\n\n' + audio
    shot = {'durationSec': 20}
    direction = {'stagePlan': [{'initialOrCarriedState': 'Fuzzby is asleep.'}]}
    result = apply(prompt, shot, direction)
    assert audio in result
    assert apply(result, shot, direction) == result
    assert 'Do not create extra' not in result
    assert VERSION


def test_missing_start_is_not_invented_and_edit_extension_scope_is_preserved():
    for prompt in ('[Edit Goal]\nReplace the sky only.', '[Extension Goal]\nContinue the action.'):
        assert apply(prompt, {}, {}) == prompt
    result = apply('[Shot Sequence]\nShot 1:\nAction: Open the door.', {}, {})
    assert '[OPENING STATE]' not in result
    assert not re.search(r'\d+[–-]\d+s', result)
