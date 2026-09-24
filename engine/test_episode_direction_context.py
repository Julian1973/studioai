"""Offline treatment-to-scene checks; these do not certify generated media quality."""
from copy import deepcopy
import json

import pytest

import cb_creative as C
import cb_departments as D
import studio_episode_direction as E
from test_cb_creative import _treatment, _selection, _scene, _beat, _card, _detail


def vision():
    return {'premise': 'A' * 9000, 'intendedFinalFeeling': 'Uneasy hope, not recovery.',
            'storyArchitecture': {'sequenceBlueprint': [
                {'sceneIds': ['S1'], 'nextQuestion': 'Will the offer be accepted?'},
                {'sceneIds': ['S9'], 'endCondition': 'A shared place, not a perfect cup.'}]},
            'visualLanguage': {key: 'Keep this decision: ' + key for key in E.VisualLanguage.model_fields},
            'provenance': {'largeAuditRecord': 'not creative context'}}


def test_complete_treatment_without_audit_noise_or_mutation():
    source = vision()
    before = deepcopy(source)
    result = json.loads(E.prompt_context(source))
    assert result['intendedFinalFeeling'] == source['intendedFinalFeeling']
    assert result['storyArchitecture'] == source['storyArchitecture']
    assert result['visualLanguage'] == source['visualLanguage']
    assert 'provenance' not in result
    result['storyArchitecture']['sequenceBlueprint'].clear()
    assert source == before
    assert E.context({}) == {}


def test_both_intake_schemas_share_optional_treatment():
    assert C.EpisodeVision.model_fields['visualLanguage'].annotation == D.EpisodeVisionDirection.model_fields['visualLanguage'].annotation
    assert C.EpisodeVision.model_fields['visualLanguage'].default is None
    assert D.EpisodeVisionDirection.model_fields['visualLanguage'].default is None
    E.VisualLanguage.model_validate(vision()['visualLanguage'])


class Captured(Exception):
    pass


@pytest.mark.parametrize('stage', ['heart', 'treatment', 'selection', 'beats', 'shots', 'review'])
def test_directing_stages_receive_ending_and_visual_language(monkeypatch, stage):
    source = vision()
    def capture(system, prompt, *args, **kwargs):
        assert E.prompt_context(source) in prompt
        raise Captured
    monkeypatch.setattr(C.cb_llm, 'structured', capture)
    monkeypatch.setattr(C.cb_llm, 'structured_with_repair', capture)
    monkeypatch.setattr(C, '_mind', lambda *args: 'offline')
    monkeypatch.setattr(C, '_characters_for', lambda *args: 'fixture canon')
    ready = {'beats': [], 'brief': '', 'cast': []}
    sd = C.SceneDirection(scene=_scene(), beats=[_beat()])
    with pytest.raises(Captured):
        if stage == 'heart':
            C.emotional_story_contract('Ep1', 1, source, ready)
        elif stage == 'treatment':
            C.gate1_treatments('Ep1', 1, source, ready)
        elif stage == 'selection':
            C.gate2_select(source, [_treatment('A')], ready)
        elif stage == 'beats':
            C.gate3_beats('Ep1', 1, source, _selection(), _treatment('A'), ready)
        elif stage == 'shots':
            C.gate4_shot_conference('Ep1', 1, _selection(), _treatment('A'), sd, vision=source)
        else:
            C.gate6_adversarial_review(source, _selection(), _treatment('A'), sd, [_card()], [])


def test_scene_review_record_preserves_treatment():
    source = vision()
    card = C.build_scene_direction_card(source, _scene(), [_beat()], [_card()], [], [_detail()])
    assert card['episodeDirection']['treatment'] == E.context(source)
    assert source == vision()
    source['visualLanguage']['lightAndColour'] = 'A different, explicitly authored progression.'
    revised = C.build_scene_direction_card(source, _scene(), [_beat()], [_card()], [], [_detail()])
    assert revised['inputSignature'] != card['inputSignature']


def test_episode_vision_reads_full_script_not_beat_summary(monkeypatch, tmp_path):
    script = tmp_path / 'approved.txt'
    script.write_text('A long pause. She opens her empty hand.\nEnd without recovery.', encoding='utf-8')
    monkeypatch.setattr(C, '_script_beats', lambda *a: ([], {}))
    monkeypatch.setattr(C.SCRIPT_STORE, 'content_path', lambda *a: script)
    monkeypatch.setattr(C, '_mind', lambda *a: 'offline')
    def capture(system, prompt, *args, **kwargs):
        assert script.read_text() in prompt
        raise Captured
    monkeypatch.setattr(C.cb_llm, 'structured', capture)
    with pytest.raises(Captured):
        C.episode_vision('Ep1')
